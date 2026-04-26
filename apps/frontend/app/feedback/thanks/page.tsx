type Props = {
  searchParams: Promise<{ sent_id?: string; rating?: string }>;
};

export default async function FeedbackThanksPage({ searchParams }: Props) {
  const params = await searchParams;
  const rating = params.rating ?? "n/a";

  return (
    <main style={{ maxWidth: 560, margin: "0 auto", padding: "48px 20px" }}>
      <h1 style={{ marginTop: 0 }}>Thank you</h1>
      <p style={{ lineHeight: 1.7 }}>
        Feedback received. Your rating <strong>{rating}</strong> has been recorded and will improve future
        message selection.
      </p>
      <p style={{ color: "#666", fontSize: 14 }}>
        You can close this tab and continue your day.
      </p>
    </main>
  );
}

