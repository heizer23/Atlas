/**
 * Chronicle ShellEntry
 *
 * Default-export React component for the Atlas Shell outlet.
 * Renders nested <Routes> (no BrowserRouter — inherits the shell's router context).
 *
 * Routes covered:
 *   /chronicle   → CalendarPage (unified heatmap calendar)
 */

import { Routes, Route } from 'react-router-dom';
import CalendarPage from './CalendarPage';

export default function ShellEntry() {
  return (
    <Routes>
      <Route path="/" element={<CalendarPage />} />
    </Routes>
  );
}
