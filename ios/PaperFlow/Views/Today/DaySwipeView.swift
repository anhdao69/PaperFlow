import SwiftData
import SwiftUI

struct DaySwipeView: View {
    let feed: DailyFeed
    let topics: TopicsIndex?
    @Environment(\.modelContext) private var modelContext
    @Query private var personalStates: [PersonalPaperState]
    @State private var session: SwipeSessionViewModel?
    @State private var detailPaper: PublicPaper?
    @State private var showsFilters = false
    @State private var actionError: String?

    var body: some View {
        Group {
            if let session {
                sessionContent(session)
            } else {
                PFLoadingShell()
            }
        }
        .padding(PFTheme.Spacing.standard)
        .background(PFTheme.background)
        .navigationTitle(PFDateText.long(feed.date))
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button("Filter", systemImage: "line.3.horizontal.decrease") {
                    showsFilters = true
                }
                .accessibilityIdentifier("swipe.filter")
            }
        }
        .sheet(isPresented: $showsFilters) {
            if let session { filterSheet(session) }
        }
        .navigationDestination(item: $detailPaper) { paper in
            if let session {
                PaperDetailView(
                    paper: paper,
                    topics: topics,
                    onSwipeSave: { try session.perform(.save) },
                    onSwipeSkip: { try session.perform(.skip) }
                )
            }
        }
        .task { makeSessionIfNeeded() }
        .onChange(of: personalStates.map(PersonalPaperStateValue.init)) { _, _ in
            session?.synchronizePersonalState()
        }
        .alert("Triage action wasn’t saved", isPresented: .constant(actionError != nil)) {
            Button("OK") { actionError = nil }
        } message: {
            Text(actionError ?? "Your previous state is unchanged.")
        }
    }

    @ViewBuilder
    private func sessionContent(_ session: SwipeSessionViewModel) -> some View {
        VStack(spacing: PFTheme.Spacing.medium) {
            let progress = session.progress
            PFProgressView(reviewed: progress.reviewed, total: progress.total)
            Text("\(session.remainingSessionCount) remaining")
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(PFTheme.textSecondary)
                .monospacedDigit()
                .frame(maxWidth: .infinity, alignment: .leading)

            if let paper = session.currentPaper {
                PFSwipeCard(
                    paper: paper,
                    topicLabels: Array(
                        PaperDetailViewModel.topicLabels(for: paper, topics: topics).prefix(3)
                    ),
                    feedback: session.feedback,
                    onDecision: { perform($0, session: session) },
                    onOpenDetail: { detailPaper = paper }
                )
                PFSwipeActionBar(
                    canUndo: session.canUndo,
                    onSkip: { perform(.skip, session: session) },
                    onUndo: { undo(session) },
                    onSave: { perform(.save, session: session) }
                )
            } else {
                TriageCompleteView(
                    progress: progress,
                    savedCount: session.savedInCollectionCount,
                    canUndo: session.canUndo,
                    onUndo: { undo(session) }
                )
            }
        }
    }

    private func filterSheet(_ session: SwipeSessionViewModel) -> some View {
        NavigationStack {
            Form {
                Section("Review Mode") {
                    Picker("Review Mode", selection: Binding(
                        get: { session.reviewMode },
                        set: { session.reviewMode = $0 }
                    )) {
                        ForEach(SwipeReviewMode.allCases) { Text($0.rawValue).tag($0) }
                    }
                    .pickerStyle(.inline)
                }
                Section("Topics") {
                    Button("All Topics") { session.selectedTopicIDs = [] }
                    ForEach(availableTopics) { topic in
                        Button {
                            if session.selectedTopicIDs.contains(topic.id) {
                                session.selectedTopicIDs.remove(topic.id)
                            } else {
                                session.selectedTopicIDs.insert(topic.id)
                            }
                        } label: {
                            HStack {
                                Text(topic.name)
                                Spacer()
                                if session.selectedTopicIDs.contains(topic.id) {
                                    Image(systemName: "checkmark")
                                }
                            }
                        }
                    }
                }
            }
            .navigationTitle("Swipe Filters")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Reset") {
                        session.reviewMode = .unreviewed
                        session.selectedTopicIDs = []
                    }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Apply") { showsFilters = false }
                }
            }
        }
        .presentationDetents([.medium, .large])
    }

    private var availableTopics: [PublicTopic] {
        let ids = Set(feed.papers.flatMap { $0.topicAssignments.map(\.topicId) })
        return (topics?.topics ?? []).filter { ids.contains($0.id) }
    }

    private func makeSessionIfNeeded() {
        guard session == nil else { return }
        let store = SwiftDataPersonalPaperStore(modelContext: modelContext)
        session = SwipeSessionViewModel(
            collection: SwipeCollection(
                id: "day-\(PFDateText.identifier(feed.date))",
                title: PFDateText.long(feed.date),
                papers: feed.papers
            ),
            store: store,
            feedback: UIKitSwipeFeedback()
        )
    }

    private func perform(_ decision: SwipeDecision, session: SwipeSessionViewModel) {
        do { try session.perform(decision) } catch {
            actionError = "Your previous personal state is unchanged."
        }
    }

    private func undo(_ session: SwipeSessionViewModel) {
        do { try session.undo() } catch {
            actionError = "There is no action available to undo."
        }
    }
}
