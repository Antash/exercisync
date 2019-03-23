#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Polar ppt xml (+ gpx) to tcx activity converter module 
# (c) Yanis Kurganov, 2015
#
# exercisync.com integration: Anton Ashmarin, 2018

import sys
import itertools
from xml.dom import minidom
from datetime import datetime, timedelta

def has_element(node, name):
    elements = [e for e in node.childNodes if e.nodeType == e.ELEMENT_NODE and e.nodeName == name]
    return len(elements) > 0

def get_element(node, name):
    elements = [e for e in node.childNodes if e.nodeType == e.ELEMENT_NODE and e.nodeName == name]
    assert 1 == len(elements)
    return elements[0]

def get_text(node, name):
    element = get_element(node, name)
    texts = [e for e in element.childNodes if e.nodeType == e.TEXT_NODE]
    assert 1 == len(texts)
    return texts[0].data

def create_element(doc, parent, name):
    element = doc.createElement(name)
    parent.appendChild(element)
    return element

def create_text_element(doc, parent, name, value):
    element = doc.createElement(name)
    element.appendChild(doc.createTextNode(str(value)))
    parent.appendChild(element)
    return element

def set_text(doc, element, value):
    element.appendChild(doc.createTextNode(str(value)))

def seconds_from_duration(duration):
    time = duration.split(':')
    assert 3 == len(time)
    secms = time[2].split('.')
    sec = int(secms[0])
    return timedelta(hours = int(time[0]), minutes = int(time[1]), seconds = sec).total_seconds()

def convert(xml, startTime, gpx=None):
#def main(exercise_name):
    #print("Converting %s..." % exercise_name)

    dateFormat = "%Y-%m-%dT%H:%M:%S.%fZ"

    # xml
    #xml_doc = minidom.parse(exercise_name + ".xml")
    xml_doc = minidom.parseString(xml)
    polar_exercise_data = xml_doc.documentElement

    calendar_item = get_element(polar_exercise_data, "calendar-items")
    assert '1' == calendar_item.getAttribute("count")

    exercise = get_element(calendar_item, "exercise")
    created = get_text(exercise, "created")
    sport_results = get_element(exercise, "sport-results")
    sport_result = get_element(sport_results, "sport-result")
    exercise_result = get_element(exercise, "result")
    exercise_hr = get_element(exercise_result, "heart-rate")

    #exercise_distance = float(get_text(exercise_result, "distance"))
    #exercise_duration = seconds_from_duration(get_text(exercise_result, "duration"))
    exercise_calories = int(get_text(exercise_result, "calories"))
    #exercise_average_hr = int(get_text(exercise_hr, "average"))
    #exercise_maximum_hr = int(get_text(exercise_hr, "maximum"))
    exercise_rr = int(get_text(exercise_result, "recording-rate"))

    exercise_laps = []
    if has_element(exercise_result, "laps"):
        exercise_laps = sorted(get_element(exercise_result, "laps").getElementsByTagName("lap"), key = lambda x: int(x.getAttribute("index")))
    else:
        # In case no laps create dummy lap with summary stats
        lap = xml_doc.createElement("lap")
        lap.appendChild(exercise_hr)
        lap.appendChild(get_element(exercise_result, "duration"))
        lap.appendChild(get_element(exercise_result, "distance"))
        exercise_laps.append(lap)


    exercise_sample_hr = []
    exercise_sample_speed = []
    exercise_sample_altitude = []

    #TODO multiple results in one xml (multisport)
    for exercise_sample in get_element(sport_result, "samples").getElementsByTagName("sample"):
        if get_text(exercise_sample, "type") == "HEARTRATE":
            exercise_sample_hr = list(map(int, filter(None, get_text(exercise_sample, "values").split(','))))
        if get_text(exercise_sample, "type") == "SPEED":
            exercise_sample_speed = list(map(lambda speed, km_h_to_m_s_coef = 0.277777777778: float(speed) * km_h_to_m_s_coef, filter(None, get_text(exercise_sample, "values").split(','))))
        if get_text(exercise_sample, "type") == "ALTITUDE":
            exercise_sample_altitude = list(map(float, filter(None, get_text(exercise_sample, "values").split(','))))

    # gpx
    #gpx_doc = minidom.parse(exercise_name + ".gpx")
    gpx_trkpts = []
    if gpx:
        gpx_doc = minidom.parseString(gpx)
        gpx = gpx_doc.documentElement

        gpx_metadata = get_element(gpx, "metadata")
        id = get_text(gpx_metadata, "time")
        gpx_trk = get_element(gpx, "trk")
        gpx_trkseg = get_element(gpx_trk, "trkseg")
        gpx_trkpts = gpx_trkseg.getElementsByTagName("trkpt")

        assert len(gpx_trkpts) == len(exercise_sample_hr)
        assert len(gpx_trkpts) == len(exercise_sample_speed)
        assert len(gpx_trkpts) == len(exercise_sample_altitude)
    else:
        # in case there is no gps track use created time as id
        id = created

    #assert 0 != len(exercise_sample_hr)

    # tcx
    tcx_doc = minidom.getDOMImplementation().createDocument(None, "TrainingCenterDatabase", None)
    training_center_database = tcx_doc.documentElement

    training_center_database.setAttribute("xsi:schemaLocation", "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2 http://www.garmin.com/xmlschemas/TrainingCenterDatabasev2.xsd")
    training_center_database.setAttribute("xmlns:ns5", "http://www.garmin.com/xmlschemas/ActivityGoals/v1")
    training_center_database.setAttribute("xmlns:ns3", "http://www.garmin.com/xmlschemas/ActivityExtension/v2")
    training_center_database.setAttribute("xmlns:ns2", "http://www.garmin.com/xmlschemas/UserProfile/v2")
    training_center_database.setAttribute("xmlns", "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2")
    training_center_database.setAttribute("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
    training_center_database.setAttribute("xmlns:ns4", "http://www.garmin.com/xmlschemas/ProfileExtension/v1")

    activities = create_element(tcx_doc, training_center_database, "Activities")
    activity = create_element(tcx_doc, activities, "Activity")
    activity.setAttribute("Sport", get_text(exercise, "sport"))
    create_text_element(tcx_doc, activity, "Id", id)

    bundle = itertools.zip_longest(gpx_trkpts, exercise_sample_hr, exercise_sample_speed, exercise_sample_altitude, fillvalue = None)
    prev_date_time = None
    total_distance = 0.0

    for exercise_lap in exercise_laps:
        lap_max_speed = 0.0
        lap_duration = 0.0
        lap_first_track_point = True
        lap_total_duration = seconds_from_duration(get_text(exercise_lap, "duration"))

        if len(exercise_sample_hr) != 0:
            exercise_lap_hr = get_element(exercise_lap, "heart-rate")
        lap_element = create_element(tcx_doc, activity, "Lap")
        create_text_element(tcx_doc, lap_element, "TotalTimeSeconds", lap_total_duration)
        distance = get_text(exercise_lap, "distance")
        if distance:
            create_text_element(tcx_doc, lap_element, "DistanceMeters", distance)
        create_text_element(tcx_doc, lap_element, "Calories", int(exercise_calories / len(exercise_laps)))
        if len(exercise_sample_hr) != 0:
            average_hr = create_element(tcx_doc, lap_element, "AverageHeartRateBpm")
            maximum_hr = create_element(tcx_doc, lap_element, "MaximumHeartRateBpm")
            create_text_element(tcx_doc, average_hr, "Value", get_text(exercise_lap_hr, "average"))
            create_text_element(tcx_doc, maximum_hr, "Value", get_text(exercise_lap_hr, "maximum"))
        create_text_element(tcx_doc, lap_element, "Intensity", "Active")
        create_text_element(tcx_doc, lap_element, "TriggerMethod", "Manual")
        track = create_element(tcx_doc, lap_element, "Track")

        for trkpt, hr, speed, altitude in iter(bundle):

            if trkpt:
                date_time_str = get_text(trkpt, "time")
                date_time = datetime.strptime(date_time_str, dateFormat)
            else:
                date_time = startTime if prev_date_time is None else prev_date_time + timedelta(0, exercise_rr)
                date_time_str = date_time.strftime(dateFormat)

            if lap_first_track_point:
                lap_first_track_point = False
                lap_element.setAttribute("StartTime", date_time_str)

            time = exercise_rr if prev_date_time is None else (date_time - prev_date_time).total_seconds()
            if speed:
                total_distance += speed * time
                lap_max_speed = max(lap_max_speed, speed)
            lap_duration += time
            prev_date_time = date_time

            trackpoint = create_element(tcx_doc, track, "Trackpoint")
            create_text_element(tcx_doc, trackpoint, "Time", date_time_str)
            if total_distance:
                create_text_element(tcx_doc, trackpoint, "DistanceMeters", total_distance)
            if altitude:
                create_text_element(tcx_doc, trackpoint, "AltitudeMeters", altitude)

            if trkpt:
                position = create_element(tcx_doc, trackpoint, "Position")
                create_text_element(tcx_doc, position, "LatitudeDegrees", trkpt.getAttribute("lat"))
                create_text_element(tcx_doc, position, "LongitudeDegrees", trkpt.getAttribute("lon"))

            if hr:
                hr_bpm = create_element(tcx_doc, trackpoint, "HeartRateBpm")
                create_text_element(tcx_doc, hr_bpm, "Value", hr)

            extensions = create_element(tcx_doc, trackpoint, "Extensions")
            tpx = create_element(tcx_doc, extensions, "TPX")
            tpx.setAttribute("xmlns", "http://www.garmin.com/xmlschemas/ActivityExtension/v2")
            if speed:
                create_text_element(tcx_doc, tpx, "Speed", speed)

            if exercise_lap != exercise_laps[-1] and lap_duration >= lap_total_duration:
                break

        if lap_max_speed:
            lap_max_speed_element = create_element(tcx_doc, lap_element, "MaximumSpeed")
            set_text(tcx_doc, lap_max_speed_element, lap_max_speed)

    for _ in iter(bundle):
        assert False

    #creator = create_element(tcx_doc, activity, "Creator")
    #creator.setAttribute("xsi:type", "Device_t")
    #create_text_element(tcx_doc, creator, "Name", "Polar RS800CX")

    author = create_element(tcx_doc, training_center_database, "Author")
    author.setAttribute("xsi:type", "Application_t")
    create_text_element(tcx_doc, author, "Name", "Polar PPT.com (xml + gpx) to Garmin (tcx) Converter")

    #with open(exercise_name + ".tcx", "wb") as tcx_file:
    #    tcx_file.write(tcx_doc.toprettyxml(indent = "    ", encoding = "utf-8"))

    return tcx_doc.toprettyxml(indent = "  ", encoding = "utf-8")
    #print("Done!")

#main(sys.argv[1])
