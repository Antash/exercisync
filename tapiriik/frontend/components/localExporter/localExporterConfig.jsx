import React from "react";
import CSRFToken from "../csrftoken";

export default class LocalExporterConfig extends React.Component {
    constructor(props) {
        super(props)
        this.state = {
            download_only_media_content: props.config.download_only_media_content
        }
    }

    toggleChecked() {
        this.setState({ download_only_media_content: !this.state.download_only_media_content });
    }

    submitForm() {
        $.post('/localExporterConfig', {'config': JSON.stringify(this.state)});
    }

    render() {
        return (
            <div>
                <h1>Local Exporter settings</h1>
                <div className="configBlock">
                    <div className="ruleRow">
                        Download only posts and photos
                        <input
                            type="checkbox" 
                            defaultChecked={this.state.download_only_media_content} 
                            onChange={this.toggleChecked.bind(this)}
                        />
                    </div>
                </div>
                <form method="POST" onSubmit={this.submitForm.bind(this)}>
                    <CSRFToken />
                    <input type="hidden" name="config" value={JSON.stringify({ download_only_media_content: this.state.download_only_media_content})} />
                    <div className="configSubmit">
                        <button type="submit">Save</button>
                    </div>
                </form>
            </div>
        )
    }
}