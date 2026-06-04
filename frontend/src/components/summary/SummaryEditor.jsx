import TextArea from "../common/TextArea.jsx";

export default function SummaryEditor({ summary, value, onChange }) {
  const text = value ?? summary?.summary_text ?? "";
  return <TextArea label="Editable draft summary" rows={14} value={text} onChange={(event) => onChange(event.target.value)} />;
}
