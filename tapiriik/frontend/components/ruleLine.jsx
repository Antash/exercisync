import React from 'react'
import Select from 'react-select'
import 'react-select/dist/react-select.css'

export default class RuleLine extends React.Component {
    state = {
        selectedSport: '',
        selectedGear: [],
    }
    handleSportChange = (selectedOption) => {
        this.setState({ selectedSport: selectedOption });
        console.log(`Selected: ${selectedOption.label}`);
    }
    handleGearChange = (selectedOption) => {
        this.setState({ selectedGear: selectedOption });
        console.log(`Selected: ${selectedOption.label}`);
    }
    render() {
        const { selectedSport, selectedGear } = this.state;
        const { sportTypes } = this.props
        const sports = sportTypes.map(function (e) {
            var obj = {};
            obj['value'] = e;
            obj['label'] = e;
            return obj;
        });
        return (
            <div className="ruleRow">
                <span className="ruleSelector">
                    <Select
                        name="sport"
                        placeholder="Select sport"
                        value={selectedSport}
                        onChange={this.handleSportChange}
                        options={sports}
                    />
                </span>
                <span className="ruleSelector">
                    <Select
                        name="inventory"
                        placeholder="Select gear(s)"
                        multi
                        value={selectedGear}
                        onChange={this.handleGearChange}
                        options={[
                            { value: 'one', label: 'One' },
                            { value: 'two', label: 'Two' },
                        ]}
                    />
                </span>
            </div>
        );
    }
}