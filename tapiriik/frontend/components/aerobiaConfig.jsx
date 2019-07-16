import React from 'react'

import CSRFToken from './csrftoken'
import RuleList from './ruleList'
import ExportConfig from './exportConfig'

const urlGears = (userid, token) =>
    `http://old15.aerobia.ru/users/${userid}/equipments?authentication_token=${token}`

class AerobiaConfig extends React.Component {
    constructor(props) {
        super(props)
        this.state = {
            gears: [],
            requestFailed: false,
            gearRules: props.config.gearRules,
            export: props.config.export
        }
    }

    componentDidMount() {
        fetch("https://cors-anywhere.herokuapp.com/" + urlGears(this.props.aerobiaId, this.props.userToken))
            .then(response => {
                if (!response.ok) {
                    throw Error("Network request failed");
                }
                return response.text();
            })
            .then(d => {
                var parser = new DOMParser();
                var page = parser.parseFromString(d, "text/html");
                var gears = [];
                var itemNodes = page.getElementsByClassName("item");
                if (!itemNodes.length) {
                    return gears;
                }
                itemNodes = Array.prototype.slice.call(itemNodes);
                itemNodes.forEach(n => {
                    var itemData = n.getElementsByTagName("p")[0];
                    itemData = itemData.getElementsByTagName("a")[0];
                    var gearUrl = itemData.getAttribute("href").split("/");
                    gears.push({
                        id: gearUrl[gearUrl.length - 1],
                        name: itemData.innerText
                    });
                });
                return gears;
            })
            .then(d => {
                this.setState({
                    gears: d
                })
            }, () => {
                this.setState({
                    requestFailed: true
                })
            })
    }

    updateExportSettings(newState) {
        this.setState({export: newState});
    }

    updateGearRules(newState) {
        this.setState({gearRules: newState.rules});
    }
    
    render() {
        const { sportTypes } = this.props;
        if (this.state.gears.length == 0)
            return (
                <div>
                    <h1>Aerobia advanced settings</h1>
                    <p>Loading gear...</p>
                </div>
            );

        return (
            <div>
                <h1>Aerobia advanced settings</h1>

                <div className="configBlock">
                    <ExportConfig 
                        data={this.state.export}
                        handleChange={(newState) => this.updateExportSettings(newState)}
                    />
                </div>
                
                <div className="fancyTable activitiesTable configBlock">
                    <p>Default gear rules:</p>
                    <RuleList 
                        data={this.state.gearRules} 
                        sportTypes={sportTypes}
                        gears={this.state.gears}
                        handleChange={(newState) => this.updateGearRules(newState)}
                    />
                </div>
                <form method="POST" action="">
                    <CSRFToken />
                    <input type="hidden" name="config" value={JSON.stringify({ gearRules: this.state.gearRules, export: this.state.export })} />
                    <div className="configSubmit">
                        <button type="submit">Save</button>
                    </div>
                </form>
            </div>
        );
    }
}

export default AerobiaConfig;
