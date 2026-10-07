import { Link } from "react-router-dom";
import type { Meta } from "../api";

/** Sources, terms and version on every page: where every number comes from, and what may be reused. */
export default function Footer({ meta }: { meta?: Meta }) {
  return (
    <footer className="site-foot">
      <div className="site-foot-inner">
        <div>
          <h2>District Evolution</h2>
          <p>India's district boundaries, 1951–2025: which district is which, where its land came from and went, and how
            to restate old statistics on today's districts.</p>
          {meta && <p className="mono muted">Release v{meta.pipeline_version} · config {meta.config_sha256.slice(0, 12)}</p>}
        </div>
        <div>
          <h2>Sources</h2>
          <ul>
            <li>Census-era boundary maps, 1951–2021: <i>District Boundaries of India</i>, ML InfoMap, via Stanford Libraries (licensed; not for redistribution).</li>
            <li>2025 boundaries: Survey of India.</li>
            <li>Administrative events: a compiled events list, used to confirm what the maps show.</li>
          </ul>
        </div>
        <div>
          <h2>Learn more</h2>
          <ul>
            <li><Link viewTransition to="/about">How it works</Link></li>
            <li><Link viewTransition to="/research">Open questions</Link></li>
            <li><Link viewTransition to="/data">Data, checks and downloads</Link></li>
            <li><a href="/docs">API reference</a></li>
          </ul>
        </div>
      </div>
    </footer>
  );
}
