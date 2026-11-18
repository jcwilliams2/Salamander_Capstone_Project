function ProgressBar({ percent, color = 'var(--status-reading)', label }) {
    const value = Math.min(100, Math.max(0, Number(percent) || 0))
    return (
        <div
            role="progressbar"
            aria-label={label}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={value}
            style={{ height: 8, borderRadius: 999, background: 'var(--surface-alt)', overflow: 'hidden' }}
        >
            <div style={{ width: `${value}%`, height: '100%', background: color, borderRadius: 999 }} />
        </div>
    )
}

export default ProgressBar