import React from 'react'

export default class ExportConfig extends React.Component {
    constructor(props) {
        super(props)
        this.state = {
            upload_media_content: props.data.upload_media_content
        }
    }

    toggleChecked() {
        this.setState({ upload_media_content: !this.state.upload_media_content }, () => {
            this.props.handleChange(this.state);
        });
    }

    render() {
        return (
            <div className="ruleRow">
                Download posts and photos
                <input
                    type="checkbox" 
                    defaultChecked={this.state.upload_media_content} 
                    onChange={this.toggleChecked.bind(this)}
                />
            </div>
        )
    }
}