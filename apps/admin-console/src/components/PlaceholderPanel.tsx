type PlaceholderPanelProps = {
  title: string;
  requiredStep: string;
  note?: string;
};

export function PlaceholderPanel({ title, requiredStep, note }: PlaceholderPanelProps) {
  return (
    <>
      <h2>{title}</h2>
      <section className="placeholder-panel" data-testid="placeholder-panel">
        <p>
          <strong>Not yet available.</strong>
        </p>
        <p>Requires Step {requiredStep}.</p>
        <p>No workflow action available.</p>
        {note ? <p className="note">{note}</p> : null}
      </section>
    </>
  );
}
