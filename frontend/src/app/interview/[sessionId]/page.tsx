interface InterviewPageProps {
  params: Promise<{
    sessionId: string;
  }>;
}

export default async function InterviewPage({ params }: InterviewPageProps) {
  const { sessionId } = await params;

  return (
    <div>
      <h1>Interview Session</h1>
      <p>Session ID: {sessionId}</p>
      <p>Placeholder for speech-to-speech interview interface.</p>
    </div>
  );
}
