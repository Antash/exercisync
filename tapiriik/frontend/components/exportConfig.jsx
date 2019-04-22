import React from 'react'

export default class ExportConfig extends React.Component {
    constructor(props) {
        super(props)
        this.state = {
            upload_media_content: props.data.upload_media_content
        }
    }

    handleCheckedChange() {
        var checkedState = !this.state.upload_media_content
        this.setState({ upload_media_content: checkedState }, () => {
            this.props.handleChange(this.state);
        });
    }

    render() {
        return (
            <div className="ruleRow">
                Загрузить все данные
                <input
                    type="checkbox" 
                    defaultChecked={this.state.upload_media_content} 
                    onChange={this.handleCheckedChange.bind(this)}
                />
            </div>
        )
    }
}