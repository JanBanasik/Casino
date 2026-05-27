import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import AuthLayout from "./components/AuthLayout";
import Layout from "./components/Layout";
import { AuthProvider } from "./hooks/useAuth";
import AccountPage from "./pages/AccountPage";
import GameTablePage from "./pages/GameTablePage";
import GamesPage from "./pages/GamesPage";
import HomePage from "./pages/HomePage";
import LiveCasinoPage from "./pages/LiveCasinoPage";
import LoginPage from "./pages/LoginPage";
import PokerTablePage from "./pages/PokerTablePage";
import PromotionsPage from "./pages/PromotionsPage";
import RegisterPage from "./pages/RegisterPage";
import RoulettePage from "./pages/RoulettePage";
import "./App.css";

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<HomePage />} />
            <Route path="/gry" element={<GamesPage />} />
            <Route path="/stoły" element={<LiveCasinoPage />} />
            <Route path="/promocje" element={<PromotionsPage />} />
            <Route path="/konto" element={<AccountPage />} />
            <Route path="/graj/:sessionId" element={<GameTablePage />} />
            <Route path="/poker/:sessionId" element={<PokerTablePage />} />
            <Route path="/poker" element={<PokerTablePage />} />
            <Route path="/roulette" element={<RoulettePage />} />
            <Route path="/dashboard" element={<Navigate to="/konto" replace />} />
            <Route path="/table/:sessionId" element={<Navigate to="/stoły" replace />} />
          </Route>

          <Route element={<AuthLayout title="Witaj z powrotem" subtitle="Zaloguj się i wróć do stołów na żywo." />}>
            <Route path="/login" element={<LoginPage />} />
          </Route>
          <Route element={<AuthLayout title="Dołącz do kasyna" subtitle="Załóż konto i usiądź przy stole." />}>
            <Route path="/register" element={<RegisterPage />} />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
