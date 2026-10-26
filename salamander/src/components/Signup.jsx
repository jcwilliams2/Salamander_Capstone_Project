import { useState, useRef } from "react"
import HCaptcha from '@hcaptcha/react-hcaptcha'
import { supabase } from "../lib/supabaseClient"

function Signup ({ onSuccess, switchToLogin }) {
    const [email, setEmail] = useState('')
    const [password, setPassword] = useState('')
    const [username, setUsername] = useState('')
    const [captchaToken, setCaptchaToken] = useState(null)
    const [errorMessage, setErrorMessage] = useState('')
    const captcha = useRef(null)

    async function handleSignup(e) {
        e.preventDefault()
        setErrorMessage('')

        if (password.length < 8) {
            setErrorMessage('Password must be at least 8 characters.')
            return
        }

        const { data: existing } = await supabase
            .from('profiles')
            .select('username')
            .eq('username', username)
            .maybeSingle()

        if (existing) {
            setErrorMessage('That username is already taken.')
            return
        }

        const { data, error } = await supabase.auth.signUp({ 
            email, 
            password,
            options: { data: { username }, captchaToken }
        })
        captcha.current?.resetCaptcha()
        setCaptchaToken(null)

        if (error) {
            if (error.message.includes('already registered')) {
                setErrorMessage('An account with this email already exists. Try logging in instead.')
            } else {
                setErrorMessage(error.message)
            }
            return
        }
        
        onSuccess(data)
    }

    return (
        <form onSubmit={handleSignup}>
            <h2>Create your account</h2>
            {errorMessage && <p style={{color: 'red'}}>{errorMessage}</p>}
            <input
                type="text"
                placeholder="Username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
            />
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
            <button type="submit" disabled={!captchaToken}>Sign Up</button>
            <p>
                Already have an account?{' '}
                <button type="button" onClick={switchToLogin}>Log in</button>
            </p>
        </form>
    )
}

export default Signup