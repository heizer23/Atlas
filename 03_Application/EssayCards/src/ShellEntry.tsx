/**
 * EssayCards — ShellEntry
 *
 * Views:
 *   /essaycards                → EssayListView
 *   /essaycards/essays/:id     → ReaderView
 *   /essaycards/review         → ReviewSessionView (no query = review/maintenance;
 *                                 query topic? | essay_id? [+ section_id?] = focus session)
 *   /essaycards/ingest         → IngestView (Sprint02: paste-JSON add/update essay)
 *   /essaycards/stats          → ReviewStatsView (study activity, scheduled-reviews
 *                                 forecast, observed recall, scheduled intervals,
 *                                 essay progress states — see CLAUDE.md "FSRS
 *                                 scheduling" and "Section progression";
 *                                 Sprint10_DualSchedulerAB's /essaycards/experiment
 *                                 route and its dashboard are retired)
 *
 * Review session note: the due queue is re-fetched from GET /flashcards/due
 * after every grade (and via a manual "Check again" on the completion screen).
 * The just-graded card is scheduled past now() by FSRS so it drops out on its
 * own; a card graded `again` reappears on a later refetch once it comes due,
 * in the server's RECENT-first order. No client-side queue, no timer, no
 * live-poll. The session ends when a refetch returns nothing due — the
 * completion screen's "Check again" re-runs the fetch for the one case that
 * leaves behind (the very last card graded `again`, with nothing else to
 * grade while its interval elapses).
 */

import React from 'react';
import { Route, Routes } from 'react-router-dom';
import { ESSAYCARDS_IMG_CSS } from './styles';
import { EssayListView } from './views/EssayListView';
import { ExploreImportView } from './views/ExploreImportView';
import { GenerateFlashcardsImportView } from './views/GenerateFlashcardsImportView';
import { ImagesView } from './views/ImagesView';
import { ImportExaminationsView } from './views/ImportExaminationsView';
import { ImportGuidedView } from './views/ImportGuidedView';
import { IngestView } from './views/IngestView';
import { NuggetAuthoringImportView } from './views/NuggetAuthoringImportView';
import { QuestionImportView } from './views/QuestionImportView';
import { QuestionOverviewView } from './views/QuestionOverviewView';
import { ReaderView } from './views/ReaderView';
import { ReviewSessionView } from './views/ReviewSessionView';
import { ReviewStatsView } from './views/ReviewStatsView';

// ── Root ──────────────────────────────────────────────────────────────────────

export default function EssayCardsApp() {
  return (
    <>
      <style>{ESSAYCARDS_IMG_CSS}</style>
      <Routes>
        <Route path="/" element={<EssayListView />} />
        <Route path="/essays/:id" element={<ReaderView />} />
        <Route path="/essays/:id/questions" element={<QuestionOverviewView />} />
        <Route path="/questions/import" element={<QuestionImportView />} />
        <Route path="/review" element={<ReviewSessionView />} />
        <Route path="/ingest" element={<IngestView />} />
        <Route path="/examinations/import" element={<ImportExaminationsView />} />
        <Route path="/guided/import" element={<ImportGuidedView />} />
        <Route path="/explore/import" element={<ExploreImportView />} />
        <Route path="/images" element={<ImagesView />} />
        <Route path="/nuggets/authoring" element={<NuggetAuthoringImportView />} />
        <Route path="/nuggets/:id/generate-flashcards" element={<GenerateFlashcardsImportView />} />
        <Route path="/stats" element={<ReviewStatsView />} />
      </Routes>
    </>
  );
}
