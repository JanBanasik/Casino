import { Outlet } from "react-router-dom";
import Navbar from "./Navbar";
import Footer from "./Footer";
import NotificationCenter from "./NotificationCenter";
import { GameActivityProvider } from "../hooks/useGameActivity";

export default function Layout() {
  return (
    <GameActivityProvider>
      <div className="site">
        <Navbar />
        <main className="site-main">
          <Outlet />
        </main>
        <Footer />
        <NotificationCenter />
      </div>
    </GameActivityProvider>
  );
}
