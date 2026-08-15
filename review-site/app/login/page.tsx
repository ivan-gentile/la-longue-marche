export const dynamic = "force-dynamic";

interface LoginSearchParams {
  [key: string]: string | string[] | undefined;
}

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<LoginSearchParams>;
}) {
  const sp = await searchParams;
  const hasError = sp.error === "1";
  const rawNext = typeof sp.next === "string" ? sp.next : "/";
  // Only same-origin relative paths are ever echoed back into the form.
  const next =
    rawNext.startsWith("/") && !rawNext.startsWith("//") && !rawNext.includes("\\")
      ? rawNext
      : "/";

  return (
    <div className="login-wrap">
      <div className="login-card">
        <h1>La Longue Marche</h1>
        <p className="login-hint">
          Review access — enter the shared password to continue.
        </p>
        <form method="post" action="/api/login">
          <input type="hidden" name="next" value={next} />
          <label htmlFor="password">Password</label>
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            autoFocus
            required
          />
          {hasError && (
            <p className="login-error">Incorrect password — please try again.</p>
          )}
          <button type="submit">Enter</button>
        </form>
      </div>
    </div>
  );
}
