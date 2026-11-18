import { useState } from 'react';
import { LockKeyhole } from 'lucide-react';

/** Optional shared-code gate shown only when the backend requires it. */
export default function AccessGate({ onUnlock }) {
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    if (!code.trim() || busy) return;
    setBusy(true);
    setError('');
    try {
      await onUnlock(code.trim());
    } catch (err) {
      setError(err.message || 'That access code was not accepted.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="access-gate">
      <form className="access-card" onSubmit={submit}>
        <span className="access-icon" aria-hidden="true"><LockKeyhole size={22} /></span>
        <h1 className="access-title">Real Estate Intelligence Assistant</h1>
        <p className="access-copy">
          This deployment is access-controlled. Enter the shared code provided by the
          project owner to explore the DarGlobal and Wasalt knowledge base.
        </p>
        <label className="sr-only" htmlFor="access-code">Access code</label>
        <input
          id="access-code"
          className="access-input"
          type="password"
          autoComplete="off"
          placeholder="Access code"
          value={code}
          onChange={(event) => setCode(event.target.value)}
        />
        {error ? <p className="access-error" role="alert">{error}</p> : null}
        <button className="access-submit" type="submit" disabled={busy || !code.trim()}>
          {busy ? 'Checking…' : 'Continue'}
        </button>
        <p className="access-footnote">Your code is kept in memory only and never stored in this browser.</p>
      </form>
    </div>
  );
}
