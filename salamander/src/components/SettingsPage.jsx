import ThemePicker from './ThemePicker'
import DigestFrequencyPicker from './DigestFrequencyPicker'
import DigestReopenButton from './DigestReopenButton'

const card = {
    background: 'var(--surface)',
    border: '1px solid var(--border)',
    borderRadius: '12px',
    padding: '16px 20px',
    marginBottom: '16px',
}
const heading = { fontSize: '1.05em', margin: '0 0 4px', fontWeight: 600, color: 'var(--text)' }
const help = { color: 'var(--text-muted)', fontSize: '0.9em', margin: '0 0 12px' }

function SettingPage({ userId }) {
    return (
        <section style={{ maxWidth: '640px', margin: '0 auto', textAlign: 'left' }}>
            <h2 style={{ textAlign: 'center' }}>Settings</h2>

            <div style={card}>
                <h3 style={heading}>Appearance</h3>
                <p style={help}>Choose how Salamander looks.</p>
                <ThemePicker userId={userId} />
            </div>

            <div style={card}>
                <h3 style={heading}>Reading variety digest</h3>
                <p style={help}>
                    A short look at how varied your reading has been, with a few books to branch out. A new digest 
                    appears the next time you open Salamander once this much time has passed since your last one.
                </p>
                <DigestFrequencyPicker userId={userId} />
                <DigestReopenButton userId={userId} />
            </div>
        </section>
    )
}

export default SettingPage