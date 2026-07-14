import { PlaceholderPanel } from "../components/PlaceholderPanel";

type PlaceholderPageProps = {
  title: string;
  requiredStep: string;
  note?: string;
};

export function PlaceholderPage({ title, requiredStep, note }: PlaceholderPageProps) {
  return <PlaceholderPanel title={title} requiredStep={requiredStep} note={note} />;
}
