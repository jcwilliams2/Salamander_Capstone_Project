import { useState, useRef } from "react"
import HCaptcha from '@hcaptcha/react-hcaptcha'
import { supabase } from "../lib/supabaseClient"

function Login({ onSuccess, switchToSignup }) {
    const [email, setEmail] = useState('')
    const [password, setPassword] = useState('')
    const [captchaToken, setCaptchaToken] = useState(null)
    const [errorMessage, setErrorMessage] = useState('')
    const captcha = useRef(null)

    async function handleLogin(e) {
        e.preventDefault()
        setErrorMessage('')

        const { data, error } = await supabase.auth.signInWithPassword({ 
            email, 
            password, 
            options: { captchaToken },
        })
        captcha.current?.resetCaptcha()
        setCaptchaToken(null)

        if (error) {
            setErrorMessage('Invalid email or password.')
            return
        }

        onSuccess(data)
    }

    return (
        <form onSubmit={handleLogin}>
            <h2>Log in</h2>
            {errorMessage && <p style={{color: 'red' }}>{errorMessage}</p>}
            <input
                type="email"
                placeholder="Email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
            />
            <input
                type="password"
                placeholder="Password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
            />
            <HCaptcha
                ref={captcha}
                sitekey={import.meta.env.VITE_HCAPTCHA_SITEKEY}
                onVerify={setCaptchaToken}
                onExpire={() => setCaptchaToken(null)}
            />
            <button type="submit" disabled={!captchaToken}>Log In</button>
            <p>
                Don't have an account?{' '}
                <button type="button" onClick={switchToSignup}>Sign up</button>
            </p>
        </form>
    )
}

export default Login