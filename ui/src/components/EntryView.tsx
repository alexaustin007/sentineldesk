import type { Sample } from "../mocks";
import { TicketInput } from "./TicketInput";

/** First screen: ticket entry only, centred. Results appear after the first submit. */
export function EntryView(p: {
  subject: string;
  body: string;
  onSubject: (v: string) => void;
  onBody: (v: string) => void;
  onSample: (s: Sample) => void;
  onSubmit: () => void;
  bodyError: boolean;
  readOnly?: boolean;
}) {
  return (
    <div className="rise mx-auto w-full max-w-[680px] px-6 pt-[8vh] pb-16">
      <div className="rounded-2xl border border-line bg-surface p-7 shadow-[0_1px_3px_rgb(0_0_0/0.05)]">
        <TicketInput
          variant="entry"
          subject={p.subject}
          body={p.body}
          onSubject={p.onSubject}
          onBody={p.onBody}
          onSample={p.onSample}
          onSubmit={p.onSubmit}
          busy={false}
          bodyError={p.bodyError}
          evidence={[]}
          readOnly={p.readOnly}
        />
      </div>
    </div>
  );
}
