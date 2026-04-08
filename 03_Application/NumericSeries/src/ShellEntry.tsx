/**
 * NumericSeries ShellEntry
 *
 * Default-export React component for the Atlas Shell outlet.
 * Renders nested <Routes> (no BrowserRouter — inherits the shell's router context).
 *
 * Routes:
 *   /series           → SeriesListPage
 *   /series/:label_id → SeriesDetailPage
 *
 * Source of truth: Sprint01/20_design/architecture.json interfaces.provides
 */

import { Routes, Route } from 'react-router-dom';
import SeriesListPage from './SeriesListPage';
import SeriesDetailPage from './SeriesDetailPage';

export default function ShellEntry() {
  return (
    <Routes>
      <Route index element={<SeriesListPage />} />
      <Route path=":label_id" element={<SeriesDetailPage />} />
    </Routes>
  );
}
