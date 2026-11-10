import { Link } from 'react-router-dom'

function BookLink({ id, children, style }) {
    if (!id) return <>{children}</>
    return (
        <Link to={`/book/${id}`} style={{ display: 'block', color: 'inherit', textDecoration: 'none', ...style }} >
            {children}
        </Link>
    )
}

export default BookLink