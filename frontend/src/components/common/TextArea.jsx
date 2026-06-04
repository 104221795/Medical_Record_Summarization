export default function TextArea({ label, ...props }) {
  return <label className="field"><span>{label}</span><textarea {...props} /></label>;
}
