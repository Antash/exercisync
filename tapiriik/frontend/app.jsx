import React from "react";
import ReactDOM from "react-dom";

import AerobiaConfig from "./components/aerobiaConfig";
import LocalExporterConfig from "./components/localExporter/localExporterConfig";
import EmptyComponent from "./components/empty";

var componentToRender;

switch(window.props.component.toLowerCase()) {
    case "aerobia":
        componentToRender = AerobiaConfig;
        break;
    case "localexporter":
        componentToRender = LocalExporterConfig;
        break;
    default:
        componentToRender = EmptyComponent;
}

ReactDOM.render(
    React.createElement(componentToRender, window.props),
    window.react_mount,
)