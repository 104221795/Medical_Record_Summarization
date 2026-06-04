import Card from "../common/Card.jsx";

export default function DocumentViewer({ documents = [] }) {
  return (
    <Card title="Clinical Documents">
      <div className="stack">
        {documents.map((doc) => (
          <article className="document-row" key={doc.document_id}>
            <strong>{doc.document_title || doc.document_type}</strong>
            <span>{doc.document_datetime || "date unavailable"}</span>
            <p>{doc.department || doc.source_system || "clinical document"}</p>
          </article>
        ))}
      </div>
    </Card>
  );
}
