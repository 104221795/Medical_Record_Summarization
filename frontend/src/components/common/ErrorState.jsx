export default function ErrorState({ error }) {
  return <div className="state error"><strong>Something went wrong</strong><p>{error?.message || String(error)}</p></div>;
}
