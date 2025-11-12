# All-Thing-Eye Frontend

Modern Next.js frontend for team activity analytics and data visualization.

## 🚀 Quick Start

### Development (Local)

```bash
cd frontend

# Install dependencies
npm install

# Set environment variables
export NEXT_PUBLIC_API_URL=http://localhost:8000

# Run development server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

### Production (Docker)

```bash
# Build and run with Docker Compose (from project root)
docker-compose up -d frontend

# Access at http://localhost:3000
```

## 📦 Tech Stack

- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **HTTP Client**: Axios
- **Charts**: Recharts
- **Icons**: Lucide React
- **Date Formatting**: date-fns

## 📁 Project Structure

```
frontend/
├── src/
│   ├── app/                  # Next.js App Router pages
│   │   ├── page.tsx         # Home/Dashboard
│   │   ├── members/         # Members pages
│   │   ├── activities/      # Activities pages
│   │   ├── projects/        # Projects pages
│   │   ├── layout.tsx       # Root layout
│   │   └── globals.css      # Global styles
│   ├── lib/
│   │   └── api.ts           # API client
│   └── types/
│       └── index.ts         # TypeScript types
├── public/                   # Static files
├── Dockerfile               # Docker build config
├── next.config.js           # Next.js configuration
├── tailwind.config.ts       # Tailwind CSS config
├── tsconfig.json            # TypeScript config
└── package.json             # Dependencies
```

## 🎨 Features

### Pages

- **Dashboard** (`/`) - Overview with statistics and activity summary
- **Members** (`/members`) - List of team members with export
- **Activities** (`/activities`) - Activity feed with filters and export
- **Projects** (`/projects`) - Project cards with export links

### Components

- Responsive navigation
- Loading states
- Error handling
- Data export (CSV/JSON)
- Source filtering
- Activity type badges

## 🔧 Environment Variables

```bash
# Backend API URL
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## 📊 API Integration

The frontend connects to the FastAPI backend at `/api/v1` endpoints:

- `GET /members` - Member list
- `GET /members/:id` - Member details
- `GET /activities` - Activities feed
- `GET /projects` - Projects list
- `GET /export/*` - Data exports

## 🐳 Docker

### Build Image

```bash
docker build -t allthingeye-frontend ./frontend
```

### Run Container

```bash
docker run -p 3000:3000 \
  -e NEXT_PUBLIC_API_URL=http://backend:8000 \
  allthingeye-frontend
```

## 📝 Development

### Adding New Pages

1. Create page in `src/app/[page-name]/page.tsx`
2. Add navigation link in `src/app/layout.tsx`
3. Create API methods in `src/lib/api.ts` if needed
4. Define types in `src/types/index.ts`

### Styling

Using Tailwind CSS utility classes:

```tsx
<div className="bg-white shadow rounded-lg p-6">
  <h2 className="text-2xl font-bold text-gray-900">Title</h2>
</div>
```

### API Calls

```tsx
import api from '@/lib/api';

// In component
const members = await api.getMembers({ limit: 100 });
```

## 🧪 Testing

```bash
# Run linter
npm run lint

# Build for production
npm run build

# Start production server
npm start
```

## 📚 Documentation

- [Next.js Documentation](https://nextjs.org/docs)
- [Tailwind CSS Documentation](https://tailwindcss.com/docs)
- [API Development Guide](../docs/API_DEVELOPMENT.md)

---

**Built with ❤️ by All-Thing-Eye Team**

