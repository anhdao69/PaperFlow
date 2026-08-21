import SwiftData
import SwiftUI

struct TopicBrowseView: View {
    @Bindable var model: AppModel
    let topic: PublicTopic

    var body: some View {
        TopicFeedLoader(model: model, relativePath: topic.feedUrl) { feed in
            TopicBrowseContent(
                feed: feed,
                topic: topic,
                subtopic: nil,
                topics: model.topicsIndex
            )
        }
        .navigationTitle(topic.name)
        .navigationBarTitleDisplayMode(.inline)
    }
}

struct SubtopicBrowseView: View {
    @Bindable var model: AppModel
    let topic: PublicTopic
    let subtopic: PublicSubtopic

    var body: some View {
        TopicFeedLoader(model: model, relativePath: subtopic.feedUrl) { feed in
            TopicBrowseContent(
                feed: feed,
                topic: topic,
                subtopic: subtopic,
                topics: model.topicsIndex
            )
        }
        .navigationTitle(subtopic.name)
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                NavigationLink {
                    TopicSwipeView(
                        model: model,
                        title: subtopic.name,
                        collectionID: "subtopic-\(subtopic.id)",
                        relativePath: subtopic.feedUrl
                    )
                } label: {
                    Label("Swipe", systemImage: "rectangle.stack")
                }
                .accessibilityIdentifier("subtopic.swipe")
            }
        }
    }
}

private struct TopicFeedLoader<Content: View>: View {
    @Bindable var model: AppModel
    let relativePath: String
    @ViewBuilder let content: (TopicFeed) -> Content

    var body: some View {
        Group {
            if let feed = model.topicFeeds[relativePath] {
                content(feed)
            } else if let error = model.topicErrors[relativePath] {
                PFErrorShell(message: error)
            } else {
                PFLoadingShell()
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(PFTheme.background)
        .task { await model.loadTopicFeed(relativePath: relativePath) }
    }
}

private struct TopicBrowseContent: View {
    let feed: TopicFeed
    let topic: PublicTopic
    let subtopic: PublicSubtopic?
    let topics: TopicsIndex?
    @State private var viewModel: TopicHistoryViewModel
    @Environment(\.modelContext) private var modelContext
    @Query private var personalStates: [PersonalPaperState]
    @State private var actionError: String?

    init(
        feed: TopicFeed,
        topic: PublicTopic,
        subtopic: PublicSubtopic?,
        topics: TopicsIndex?
    ) {
        self.feed = feed
        self.topic = topic
        self.subtopic = subtopic
        self.topics = topics
        _viewModel = State(
            initialValue: TopicHistoryViewModel(feed: feed, topic: topic, subtopic: subtopic)
        )
    }

    var body: some View {
        let visible = viewModel.visiblePapers(personalStates: personalStates)
        ScrollView {
            LazyVStack(alignment: .leading, spacing: PFTheme.Spacing.medium) {
                Text(
                    "\(feed.totalPaperCount) "
                        + (feed.totalPaperCount == 1 ? "paper" : "papers")
                        + " in full history"
                )
                    .font(.headline)
                    .monospacedDigit()
                    .accessibilityIdentifier("topic.history.total")
                if !viewModel.dayCounts.isEmpty {
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack {
                            ForEach(viewModel.dayCounts, id: \.date) { day in
                                PFTag(text: "\(PFDateText.short(day.date)) · \(day.count)")
                            }
                        }
                    }
                    .accessibilityIdentifier("topic.history.days")
                }
                controls
                Text("\(visible.count) shown")
                    .font(.subheadline)
                    .foregroundStyle(PFTheme.textSecondary)
                    .monospacedDigit()
                if visible.isEmpty {
                    PFEmptyShell(
                        title: feed.totalPaperCount == 0 ? "No papers yet" : "No matching papers",
                        message: feed.totalPaperCount == 0
                            ? "This published topic history is currently empty."
                            : "Adjust the local review-state or subtopic filter."
                    )
                } else {
                    ForEach(visible) { paper in
                        paperRow(paper)
                    }
                }
            }
            .padding(PFTheme.Spacing.standard)
        }
        .background(PFTheme.background)
        .alert("Personal state wasn’t updated", isPresented: .constant(actionError != nil)) {
            Button("OK") { actionError = nil }
        } message: {
            Text(actionError ?? "")
        }
    }

    private var controls: some View {
        VStack(alignment: .leading, spacing: PFTheme.Spacing.small) {
            if subtopic != nil {
                Picker("Paper Status", selection: $viewModel.status) {
                    Text("All Papers").tag(DayBrowseStatus.all)
                    Text("Unread").tag(DayBrowseStatus.unread)
                    Text("Saved").tag(DayBrowseStatus.saved)
                }
                .pickerStyle(.segmented)
            } else {
                Menu("Status: \(viewModel.status.rawValue)") {
                    ForEach(DayBrowseStatus.allCases) { status in
                        Button(status.rawValue) { viewModel.status = status }
                    }
                }
                if !topic.subtopics.isEmpty {
                    Menu("Subtopics") {
                        Button("All Subtopics") { viewModel.selectedSubtopicIDs = [] }
                        ForEach(topic.subtopics) { item in
                            Button {
                                if viewModel.selectedSubtopicIDs.contains(item.id) {
                                    viewModel.selectedSubtopicIDs.remove(item.id)
                                } else {
                                    viewModel.selectedSubtopicIDs.insert(item.id)
                                }
                            } label: {
                                if viewModel.selectedSubtopicIDs.contains(item.id) {
                                    Label(item.name, systemImage: "checkmark")
                                } else {
                                    Text(item.name)
                                }
                            }
                        }
                    }
                }
            }
            Menu("Sort: \(viewModel.sort.rawValue)") {
                ForEach(DayBrowseSort.allCases) { sort in
                    Button(sort.rawValue) { viewModel.sort = sort }
                }
            }
        }
        .buttonStyle(.bordered)
    }

    private func paperRow(_ paper: PublicPaper) -> some View {
        let state = personalState(for: paper)
        return VStack(alignment: .trailing, spacing: PFTheme.Spacing.small) {
            NavigationLink {
                PaperDetailView(paper: paper, topics: topics)
            } label: {
                PFPaperBrowseCard(
                    paper: paper,
                    topicLabels: Array(
                        PaperDetailViewModel.topicLabels(for: paper, topics: topics).prefix(2)
                    ),
                    isReviewed: state?.seen == true,
                    isSaved: state?.saved == true
                )
            }
            .buttonStyle(.plain)
            Button {
                toggleSave(paper, state: state)
            } label: {
                Label(
                    state?.saved == true ? "Unsave" : "Save",
                    systemImage: state?.saved == true ? "bookmark.fill" : "bookmark"
                )
            }
            .buttonStyle(.bordered)
            .accessibilityIdentifier("topic.paper.save.\(paper.arxivId)")
        }
    }

    private func personalState(for paper: PublicPaper) -> PersonalPaperState? {
        let id = PublicPaper.normalizeArxivID(paper.arxivId)
        return personalStates.first { $0.canonicalArxivID == id }
    }

    private func toggleSave(_ paper: PublicPaper, state: PersonalPaperState?) {
        do {
            let actions = PersonalActionService(
                store: SwiftDataPersonalPaperStore(modelContext: modelContext)
            )
            if state?.saved == true {
                try actions.unsave(arxivID: paper.arxivId)
            } else {
                try actions.save(paper)
            }
        } catch {
            actionError = "Your previous personal state is unchanged."
        }
    }
}
