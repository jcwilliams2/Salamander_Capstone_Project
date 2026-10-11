import { EXPLORE_LEVELS } from "../lib/exploreLevels"

function ExplorationControl({ level, onChange }) {
    return (
        <div style={{ maxWidth: '420px', margin: '0 auto 16px', textAlign: 'center' }}>
            <label htmlFor="explore-slider"><strong>How adventurous?</strong></label>
            <input
                id="explore-slider"
                type="range"
                min={0}
                max={EXPLORE_LEVELS.length - 1}
                step={1}
                value={level}
                onChange={(e) => onChange(Number(e.target.value))}
                aria-valuetext={EXPLORE_LEVELS[level].label}
                style={{ width: '100%' }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85em' }}>
                {EXPLORE_LEVELS.map((l, i) => (
                    <span key={l.label} style={{ fontWeight: i === level ? 'bold' : 'normal' }}>{l.label}</span>
                ))}
            </div>
            <div style={{ fontSize: '0.85em', color: '#666' }}>{EXPLORE_LEVELS[level].hint}</div>
        </div>
    )
}

export default ExplorationControl