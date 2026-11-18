import { ArrowLeftRight, Building2, Gem, HelpCircle, Home, MapPin } from 'lucide-react';
import { EXAMPLE_QUESTIONS } from '../constants.js';

const ICONS = [Building2, MapPin, Home, ArrowLeftRight, Gem, HelpCircle];

export default function WelcomeScreen({ onExample }) {
  return (
    <div className="welcome">
      <div className="welcome-inner">
        <p className="welcome-eyebrow">DarGlobal × Wasalt intelligence</p>
        <h1 className="welcome-title">Real estate questions, answered with sources.</h1>
        <p className="welcome-subtitle">
          Ask about projects, listings, locations and amenities across both portfolios. Every answer is
          grounded in retrieved property records — with the sources shown beneath it.
        </p>
        <div className="welcome-context">
          <p>DarGlobal — archived public snapshots of project pages (no prices published).</p>
          <p>
            Wasalt — captured listing pages with prices as listed, not live availability. Filters and
            follow-ups refine your results.
          </p>
        </div>
        <div className="welcome-grid">
          {EXAMPLE_QUESTIONS.map((example, index) => {
            const Icon = ICONS[index % ICONS.length];
            return (
              <button
                key={example.label}
                type="button"
                className="example-card"
                onClick={() => onExample(example.question)}
              >
                <span className="example-icon" aria-hidden="true">
                  <Icon size={16} strokeWidth={1.6} />
                </span>
                <span className="example-copy">
                  <span className="example-tag">{example.tag}</span>
                  <span className="example-question">{example.question}</span>
                </span>
              </button>
            );
          })}
        </div>
        <p className="welcome-footnote">
          Answers reflect the indexed data snapshot only. Always verify live availability with the source.
        </p>
      </div>
    </div>
  );
}
