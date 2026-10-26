import { useRef, useState } from 'react'
import HCaptcha from '@hcaptcha/react-hcaptcha'
import { supabase } from '../lib/supabaseClient'

const CONSENT_VERSION = '2026-10-v1'

function StudyEntry({ onStarted, onLogin }) {
    const [step, setStep] = useState('consent')
    const [isAdult, setIsAdult] = useState(false)
    const [agreed, setAgreed] = useState(false)
    const [captchaToken, setCaptchaToken] = useState(null)
    const [busy, setBusy] = useState(false)
    const [error, setError] = useState('')
    const captcha = useRef(null)

    async function start() {
        setBusy(true)
        setError('')

        const { data, error: signInError } = await supabase.auth.signInAnonymously({
            options: { captchaToken },
        })
        captcha.current?.resetCaptcha()
        setCaptchaToken(null)
        if (signInError) {
            setBusy(false)
            setError(signInError.message)
            return
        }

        const { error: consentError } = await supabase
            .from('study_consent')
            .insert({ user_id: data.user.id, consent_version: CONSENT_VERSION })
        if (consentError) {
            await supabase.auth.signOut()
            setBusy(false)
            setError("We couldn't record your consent, so the session was not started. Please try again.")
            return
        }

        setBusy(false)
        onStarted(data.user.id)
    }

    if (step === 'declined') {
        return (
            <div style={{ maxWidth: '640px', margin: '32px auto', textAlign: 'center' }}>
                <h2>Thank you</h2>
                <p>You chose not to take part, and no data was collected. You can close this page.</p>
            </div>
        )
    }

    if (step === 'verify'){
        return (
            <div style={{ maxWidth: '640px', margin: '32px auto', textAlign: 'center' }}>
                <h2>One last step</h2>
                <p>Please confirm you're a person, then start the session.</p>
                <HCaptcha
                    ref={captcha}
                    sitekey={import.meta.env.VITE_HCAPTCHA_SITEKEY}
                    onVerify={setCaptchaToken}
                    onExpire={() => setCaptchaToken(null)}
                />
                <button type="button" disabled={!captchaToken || busy} onClick={start} style={{ marginTop: '16px' }}>
                    {busy ? 'Starting...' : 'Start'}
                </button>
                {error && <p style={{ color: 'red' }}>{error}</p>}
            </div>
        )
    }

    return (
        <div style={{ maxWidth: '640px', margin: '32px auto', textAlign: 'left' }}>
            <h2 style={{ textAlign: 'center' }}>Salamander reading study: consent</h2>

            <p><strong>What this study is.</strong> You are being invited to try Salamander, a prototype web app that recommends books, and to answer a short survey about the recommendations. The study compares two versions of how the app handles variety (diversity) in its recommendations. You will be randomly assigned to one version and you won't be told which one. Both versions are fully working.</p>

            <p><strong>What you will do.</strong> Browse book recommendations, mark books as interesting or not interesting, and then complete a survey of about 10 minutes. The whole session takes about 15 to 20 minutes. You do it on your own, at your own pace, and no researcher is present.</p>

            <p><strong>Your privacy.</strong> Participation is anonymous. We do not ask for your name or email. Your clicks, ratings, settings and survey answers are linked only to a randomly generated session ID, not to your identity. Data is stored on a password-protected, encrypted drive that only the researcher can access, and it is deleted after the capstone is completed and archived. Results may be reported in aggregate in a capstone project and may be shared externally.</p>

            <p><strong>Risks and benefits.</strong> We expect minimal risk, no greater than normal web browsing. You may discover books or authors outside your usual reading. There is no payment or compensation.</p>

            <p><strong>Taking part is your choice.</strong> You can close your browser at any time, even mid-session, with no penalty and no need to give a reason.</p>

            <p><strong>Questions.</strong> Researcher: Jerlisa Williams, M.S. Computer Science, Full Sail University, jcwilliams14@student.fullsail.edu.</p>

            <label style={{ display: 'block', margin: '12px 0' }}>
                <input type="checkbox" checked={isAdult} onChange={(e) => setIsAdult(e.target.checked)} />{' '}
                I am 18 years of age or older.
            </label>
            <label style={{ display: 'block', margin: '12px 0' }}>
                <input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} />{' '}
                I have read this information and I agree to take part.
            </label>

            <div style={{ textAlign: 'center', marginTop: '16px' }}>
                <button type="button" disabled={!isAdult || !agreed} onClick={() => setStep('verify')}>
                    I agree. Continue
                </button>{' '}
                <button type="button" onClick={() => setStep('declined')}>
                    No thanks
                </button>
                {onLogin && (
                    <p style={{ textAlign: 'center', marginTop: '24px' }}>
                        Already have an account?{' '}
                        <button type="button" onClick={onLogin}>Log in</button>
                    </p>
                )}
            </div>
        </div>
    )
}

export default StudyEntry