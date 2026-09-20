interface ReportPageProps {
  params: Promise<{
    sessionId: string;
  }>;
}

export default async function ReportPage({ params }: ReportPageProps) {
  const { sessionId } = await params;

  return (
    <div>
      <h1>Interview Report</h1>
      <p>Session ID: {sessionId}</p>
      <p>Placeholder for performance report and feedback analysis.</p>
    </div>
  );
}
