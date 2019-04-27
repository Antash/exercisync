import React from 'react'

export default class ExportConfig extends React.Component {
    constructor(props) {
        super(props)
        this.state = {
            upload_media_content: props.data.upload_media_content
        }
    }

    handleCheckedChange(newState) {
        this.setState({ upload_media_content: newState }, () => {
            this.props.handleChange(this.state);
        });
    }

    render() {
        return (
            <div className="ruleRow">
                Загрузить записи из ленты
                <input
                    type="checkbox" 
                    defaultChecked={this.state.upload_media_content} 
                    onChange={(newState) => this.handleCheckedChange(newState)}
                />
            </div>
        )
    }
}