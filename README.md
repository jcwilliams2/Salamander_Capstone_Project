# Salamander

*A reading app that recommends your next book—and then asks whether you're only ever reading more of the same.*

Salamander is my M.S. Computer Science capstone at Full Sail University. It's a personal library app built around one tension: recommendations that feel **relevant** versus recommendations that keep your reading **diverse**. The name is wordplay—"book worm" meets "book dragon," and the salamander sits right between them.

**Live demo:** [salamander-capstone-project.vercel.app](https://salamander-capstone-project.vercel.app)

## The question behind it

> How can an AI-based recommendation system improve recommendation relevance for cold-start users while maintaining sufficient diversity within the recommendations?

Cold start is the hard part—a brand-new reader has no history, so the system has to say something useful anyway. Salamander tries to do that without trapping them in one genre forever.

## How it works

Every book lives in one shared embedding space—its description is embedded with the pretrained `all-MiniLM-L6-v2` sentence-transformer (not fine-tuned) and stored in Supabase.

Two centroids are built from that space, and they do different jobs:

- **A feedback-weighted centroid** drives recommendations. Likes pull it toward a book, dislikes push it away.
- **An unweighted centroid** drives the diversity audit. It shows where your reading actually sits, so the app can point at the gaps.

For brand-new users, an onboarding survey (genres, or a few seed books) stands in for history. Skip the survey and you get current New York Times bestsellers instead. A user-facing **exploration control** lets readers dial how far from their comfort zone the feed is allowed to wander.

## What you can do in the app

- Browse, search, and filter the catalog by genre
- Add a book that isn't in the catalog—look it up by title or ISBN and the backend pulls the metadata in (Open Library first, then ISBNdb, then Google Books to fill gaps)
- Track every book as *want to read*, *reading*, *finished*, or *did not finish*, and give it a thumbs up or down
- Keep a reading log with editable start and finish dates
- Set a yearly reading goal and see your pace against it
- See reading stats, including a genre breakdown
- Generate a shareable, theme-aware "Month in Books" card
- Get diversity picks—books chosen to stretch your usual shelf
- Switch themes, including light and dark

## Study mode

Salamander also doubles as the instrument for my capstone user study. Participants can join anonymously, give consent, and get randomly assigned to one of two recommendation conditions. After rating a set of books they complete a short survey. Consent, assignments, and responses live in their own tables (see `salamander-backend/sql/study_schema.sql`), and hCaptcha guards sign-up and study entry.

## Tech stack

| Layer | Tools |
| --- | --- |
| Frontend | React 19, Vite, React Router, Recharts, hCaptcha |
| Backend | FastAPI (Python), sentence-transformers, NumPy |
| Data and auth | Supabase—Postgres, Auth (including anonymous sign-in), pgvector |
| Book data | Open Library, ISBNdb, Google Books, NYT Books API |
| Hosting | Vercel (frontend), Railway (backend) |

## Repo layout

```
Salamander_Capstone_Project/
├── salamander/            # React + Vite frontend
│   └── src/
│       ├── components/    # pages and UI pieces
│       ├── lib/           # Supabase client, API base URL, exploration levels
│       └── theme/         # theme definitions
└── salamander-backend/    # FastAPI backend
    ├── main.py            # API entry point
    ├── recommend.py       # cold-start + personalized recommendations
    ├── collaborative.py   # collaborative and hybrid strategies
    ├── ingest.py          # book metadata + embeddings
    └── sql/               # study tables
```

## Run it locally

You'll need Node 22, Python 3.12, and a Supabase project.

**Backend**

```bash
cd salamander-backend
python -m venv venv
venv\Scripts\activate          # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload      # http://localhost:8000
```

Create `salamander-backend/.env` with:

| Variable | What it's for |
| --- | --- |
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Server-side key—never expose it to the frontend |
| `ISBNDB_API_KEY` | ISBNdb metadata |
| `NYT_API_KEY` | NYT bestseller list |
| `GOOGLE_BOOKS_API_KEY` | Google Books metadata |
| `FRONTEND_ORIGIN` | The frontend's URL, for CORS (`http://localhost:5173` is always allowed) |
| `STUDY_PILOT` | Optional—set to `1` to balance the two study conditions instead of assigning randomly |

The first start downloads the embedding model, so give it a minute.

**Frontend**

```bash
cd salamander
npm install
npm run dev                    # http://localhost:5173
```

Create `salamander/.env` with:

| Variable | What it's for |
| --- | --- |
| `VITE_SUPABASE_URL` | Your Supabase project URL |
| `VITE_SUPABASE_ANON_KEY` | Public anon key |
| `VITE_HCAPTCHA_SITEKEY` | hCaptcha site key |
| `VITE_API_URL` | Backend URL—leave it out locally and it defaults to `http://localhost:8000` |

## Deploying

- **Backend → Railway.** Root directory `salamander-backend`, start command `uvicorn main:app --host 0.0.0.0 --port $PORT`, and the backend variables above. Set `FRONTEND_ORIGIN` to the Vercel URL with no trailing slash.
- **Frontend → Vercel.** Root directory `salamander`, Vite preset, and the frontend variables above with `VITE_API_URL` pointing at the Railway domain. `vercel.json` rewrites every path to `index.html` so deep links like `/catalog` survive a refresh.
- **Supabase.** Add the Vercel URL as the Site URL and a redirect URL under Authentication, and keep anonymous sign-ins on for study participants.

## What's next

Individual book pages, a "why you might like this" explanation on every recommendation card, and—the part I'm most curious about—recommendations that learn from reading behavior instead of only explicit ratings.

## Author

Jerlisa Williams—M.S. Computer Science, Full Sail University. [GitHub](https://github.com/jcwilliams2)

*Can a recommender really widen your reading if it's also trying to be right about what you'll like?* That's the tension this whole project is poking at, and I don't think it's settled yet.