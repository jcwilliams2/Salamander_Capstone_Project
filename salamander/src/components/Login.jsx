import { useState } from "react"
import { supabase } from "../lib/supabaseClient"

function Login({ onSuccess, switchToSignup }) {
    const [email, setEmail] = useState('')
    const [password, setPassword] = useState('')
    const [errorMessage, setErrorMessage] = useState('')

    async function handleLogin(e) {
        e.preventDefault()
        setErrorMessage('')

        const { data, error } = await supabase.auth.signInWithPassword({ email, password })

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
            <button type="submit">Log In</button>
            <p>
                Don't have an account?{' '}
                <button type="button" onClick={switchToSignup}>Sign up</button>
            </p>
        </form>
    )
}

export default Login