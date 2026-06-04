import Card from "../../components/common/Card.jsx";
import SummaryProviderSelector from "../../components/summary/SummaryProviderSelector.jsx";

export default function SettingsPage() {
  return (
    <Card title="Settings">
      <p>Provider availability is controlled by backend environment and governance flags.</p>
      <SummaryProviderSelector value="deterministic" onChange={() => {}} />
    </Card>
  );
}
