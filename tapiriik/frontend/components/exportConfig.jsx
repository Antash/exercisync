import React from 'react'

export default class ExportConfig extends React.Component {
    constructor(props) {
        super(props)
        this.state = {
            upload_media_content: props.data.upload_media_content,
            min_report_length: props.data.min_report_length
        }
    }

    toggleChecked() {
        this.setState({ upload_media_content: !this.state.upload_media_content }, () => {
            this.props.handleChange(this.state);
        });
    }

    lengthChanged(e) {
        this.setState({ min_report_length: parseInt(e.target.value) }, () => {
            this.props.handleChange(this.state);
        });
    }

    render() {
        return (
            <div>
                <div className="ruleRow">
                    Загружать только фотографии и отчеты
                    <input
                        type="checkbox" 
                        defaultChecked={this.state.upload_media_content} 
                        onChange={this.toggleChecked.bind(this)}
                    />
                </div>
                <div className="ruleRow">
                    Игнорировать отчеты без фотографий короче 
                    <input
                        type="text"
                        defaultValue={this.state.min_report_length}
                        onChange={this.lengthChanged.bind(this)}
                    />
                    символов
                </div>
            </div>
        )
    }
}