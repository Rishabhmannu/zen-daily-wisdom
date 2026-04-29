type Props = {
  searchParams: Promise<{ sent_id?: string; rating?: string }>;
};

export default async function FeedbackThanksPage({ searchParams }: Props) {
  const params = await searchParams;
  const rating = params.rating ?? "n/a";

  return (
    <main className="zen-shell zen-auth-shell">
      <section className="zen-card">
        <h1 className="zen-title">Thank you</h1>
        <p className="zen-subtitle">
          Feedback received. Your rating <strong>{rating}</strong> has been recorded and will improve future
          message selection.
        </p>
        <p className="zen-note">You can close this tab and continue your day.</p>
      </section>
    </main>
  );
}

