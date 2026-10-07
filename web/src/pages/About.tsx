import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import Term from "../components/Term";
import { fmt, get, type Check, type Overview } from "../api";
import { GLOSSARY, METHOD, type TermKey } from "../glossary";

const P = (n: number) => `${Math.round(n * 100)}%`;

/** How the answers are worked out, in plain language. Thresholds come from METHOD (checked against config). */
export default function About() {
  const { data: o } = useQuery({ queryKey: ["overview"], queryFn: () => get<Overview>("/overview") });
  const { data: v } = useQuery({ queryKey: ["validation"], queryFn: () => get<{ checks: Check[] }>("/validation") });
  const errors = v?.checks.filter((c) => c.severity === "ERROR") ?? [];
  const failing = errors.filter((c) => c.n_violations > 0);
  const evTotal = o?.events.reduce((a, e) => a + e.events, 0);
  const evMeasured = o?.events.filter((e) => e.status === "MEASURED").reduce((a, e) => a + e.events, 0);

  return (
    <main className="page prose-page" data-testid="about-page">
      <div className="page-head">
        <p className="eyebrow">Methods</p>
        <h1>How it works</h1>
        <p className="lede">Where every answer on this site comes from, how it is decided, and how far it can be trusted. No figure is
          estimated by hand; each one is read from tables that the pipeline builds and checks on every run.</p>
      </div>

      <nav className="toc" aria-label="On this page">
        <a href="#sources">The sources</a><a href="#identity">Same district or new one?</a><a href="#land">Where land went</a>
        <a href="#events">Events and how exact they are</a><a href="#restate">Restating statistics</a><a href="#limits">Limits</a>
        <a href="#checks">Checks</a><a href="#glossary">Glossary</a>
      </nav>

      <section id="sources">
        <h2>1. The sources</h2>
        <p><b>Nine boundary maps.</b> Census-era district maps for 1951, 1961, 1971, 1981, 1991, 2001, 2011 and 2021, and the Survey of
          India map of 2025. They are the only thing that decides which land belonged to which district. Boundaries are known on these
          nine dates and nowhere in between, so every change is placed in a <Term k="window">window</Term> between two maps.</p>
        <p><b>An events list.</b> A compiled list of dated administrative changes{evTotal ? <>, which the pipeline groups into
          {" "}{fmt(evTotal)} events</> : null}. It says that a change happened, roughly when, and what it was called. It is used to
          confirm and date what the maps show, never to override them.</p>
        <p><b>Curated reference tables.</b> Renames and spellings, state reorganisations, and confirmed problems with particular maps,
          each row with its evidence. These are edited by people, reviewed like code, and only confirmed rows are used.</p>
      </section>

      <section id="identity">
        <h2>2. Is it the same district, or a new one?</h2>
        <p>Every two consecutive maps are laid over each other, cutting India into pieces that each belong to one district on the earlier
          map and one on the later map. For each earlier district the pipeline then asks two things about the later district that
          received most of its land: what share of the earlier district went there, and what share of the later district came from it.</p>
        <ul className="rules">
          <li><b>It carries on</b> when at least {P(METHOD.strongShare)} of its land goes into one later district that is mostly
            (at least {P(METHOD.coreShare)}) made of it. A new name does not matter: Poona becoming Pune is still the same district.</li>
          <li><b>It also carries on after losing land</b> when a later district is mostly made of its land, holds at least
            {" "}{P(METHOD.nameRetainedShare)} of it, and keeps its name. This is a district that had another carved out of it: Kangra had four
            districts carved out of it and is one district from 1951 to 2025.</li>
          <li><b>It carries on when it grows</b>, if at least {P(METHOD.strongShare)} of it stays together, it keeps its name, and no other
            district carries on into the same place.</li>
          <li><b>Otherwise it ends</b>, and the districts that received its land are new districts, linked back to it.</li>
        </ul>
        <p>A district that carries on keeps one <Term k="identity">identity</Term> and one <Term k="key">key</Term> (such as IND-000202)
          across all its maps. Names only break ties when the land alone cannot decide; a district is never matched on its name alone.</p>
        {o && <p className="callout">Result: <b>{fmt(o.identities.total)}</b> district identities across the nine maps, of which
          {" "}<b>{fmt(o.identities.active)}</b> are on the 2025 map and <b>{fmt(o.identities.closed)}</b> ended along the way.</p>}
      </section>

      <section id="land">
        <h2>3. Where the land went</h2>
        <p>Every piece of the overlay gets exactly one label, so every square kilometre is accounted for once:</p>
        <ul className="rules">
          <li><b>Stayed</b> in the same district.</li>
          <li><b>Went to a new district</b>: <Term k="carved">carved out</Term> (the old district carried on), <Term k="split">split</Term>
            {" "}(it did not), <Term k="merged">merged</Term> or <Term k="restored">restored</Term>.</li>
          <li><b>Moved between two districts that both carried on</b>: a <Term k="transfer">transfer</Term>.</li>
          <li><b>Drawing difference</b>: strips narrower than {METHOD.displacementWidthKm} km where the two maps trace one border
            differently (<Term k="displacement">boundary displacement</Term>), and tiny slivers the overlay leaves (under{" "}
            {METHOD.sliverKm2} km², or 0.01% of a large district). These are not counted as land changing hands.</li>
        </ul>
        <p>Areas are measured on the curved surface of the earth (the WGS84 ellipsoid), and checked against a second, independent
          implementation on every build. For each district and window the accounts add up exactly: area before equals land kept, plus
          land given away, plus drawing differences, plus any land that lies in no district on the later map.</p>
      </section>

      <section id="events">
        <h2>4. Events, and how exact their areas are</h2>
        <p>An event is linked to the districts it names only within land that actually moved on the maps, so a name cannot pull in a
          district from elsewhere. Its area is then one of three things:</p>
        <ul className="rules">
          <li><Term k="measured">Measured</Term>: the only event touching those districts between two maps, so the land that moved is its land alone.</li>
          <li><Term k="bounded">Bounded</Term>: two or more events share that window, so only their combined area is known.</li>
          <li><Term k="notMeasurable">Not measurable</Term>: its parent district is not on the maps.</li>
        </ul>
        {evTotal && evMeasured != null && <p className="callout"><b>{fmt(evMeasured)}</b> of {fmt(evTotal)} events are measured exactly.</p>}
        <p>Where the events list and the maps disagree, nothing is corrected automatically: the disagreement becomes an
          {" "}<Link viewTransition to="/research">open question</Link> for a person to settle with documents.</p>
      </section>

      <section id="restate">
        <h2>5. Restating statistics on the 2025 districts</h2>
        <p>Overlaying each earlier map directly on the 2025 map (never chaining through the maps in between) gives the
          {" "}<Term k="crosswalk">crosswalk</Term>: the share of each past district's land inside each 2025 district. A total reported
          for a past district, such as crop area or production, is shared out in those proportions.</p>
        <ul className="rules">
          <li><b>Only totals are shared out.</b> A rate such as yield is never split; it is recomputed from the restated totals
            (production divided by area).</li>
          <li><b>The assumption is stated on every value.</b> Sharing by area assumes the quantity is spread evenly over the land. That is
            exact for area itself and can be wrong for crops; a cropland-based method can be added when a cropland map is supplied.</li>
          <li><b>Nothing is filled in.</b> If some districts did not report, the 2025 district's <Term k="coverage">coverage</Term> drops
            below 100%; no value is invented for the missing part.</li>
        </ul>
        <p><Link viewTransition to="/crosswalk">See the crosswalk</Link> or <Link viewTransition to="/harmonize">restate your own file</Link>.</p>
      </section>

      <section id="limits">
        <h2>6. Limits you should know about</h2>
        <ul className="rules">
          <li><b>“2025 districts” means the Survey of India 2025 map.</b> It does not yet show Andhra Pradesh's 2022 or Rajasthan's 2023
            new districts, or Mizoram's 2019 ones, so statistics restated there land on the older units.</li>
          <li><b>Different map editions draw the same border differently.</b> The 2011 map in particular traces many borders afresh, so
            some land appears to move when it did not. Strips under {METHOD.displacementWidthKm} km wide are set aside as drawing differences, but wider
            differences can remain.</li>
          <li><b>Some land is on no 2025 district.</b> Statistics for that land cannot be restated; the Crosswalk page shows how much of
            each past district is covered.</li>
          <li><b>The events list cites no primary documents</b> such as gazette notifications, which is why it only confirms the maps and
            why its disagreements stay open.</li>
          <li><b>The census-era maps are licensed.</b> They may not be redistributed, so this platform is private and the data are not
            published.</li>
        </ul>
      </section>

      <section id="checks">
        <h2>7. Checks on every build</h2>
        <p>Each build runs a set of automatic checks: the maps tile India without overlaps, the overlays account for every square
          kilometre, the two independent area calculations agree, no district descends from itself, and restated statistics neither
          gain nor lose any quantity. A build that fails any error-level check is not released.</p>
        {v && <p className="callout">This release: <b>{fmt(v.checks.length)}</b> checks, <b>{failing.length === 0 ? "all" : fmt(errors.length - failing.length)}</b>
          {" "}error-level checks passing. <Link viewTransition to="/data">See every check →</Link></p>}
      </section>

      <section id="glossary">
        <h2>Glossary</h2>
        <dl className="glossary">
          {(Object.keys(GLOSSARY) as TermKey[]).map((k) => (
            <div key={k}><dt>{GLOSSARY[k].term}</dt><dd>{GLOSSARY[k].text}</dd></div>))}
        </dl>
      </section>
    </main>
  );
}
