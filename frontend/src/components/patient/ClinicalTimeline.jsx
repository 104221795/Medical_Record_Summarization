import Card from "../common/Card.jsx";

export default function ClinicalTimeline({ encounters = [] }) {
  return (
    <Card title="Clinical Timeline">
      <div className="timeline">
        {encounters.map((item) => (
          <div className="timeline-item" key={item.encounter_id}>
            <strong>{item.encounter_type || item.department || "Encounter"}</strong>
            <span>{item.start_time || "date unavailable"}</span>
            <p>{item.reason_for_visit || item.status || "No encounter summary."}</p>
          </div>
        ))}
      </div>
    </Card>
  );
}
