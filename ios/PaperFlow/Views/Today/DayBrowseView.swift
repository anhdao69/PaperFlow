import SwiftData
import SwiftUI

struct DayBrowseView: View {
    let feed: DailyFeed
    let topics: TopicsIndex?
    @State private var viewModel: DayBrowseViewModel
    @State private var showsFilters = false
    @State private var actionError: String?
    @Environment(\.modelContext) private var modelContext
    @Query private var personalStates: [PersonalPaperState]

    init(feed: DailyFeed, topics: TopicsIndex?) {
        self.feed = feed
        self.topics = topics
        _viewModel = State(initialValue: DayBrowseViewModel(feed: feed, topics: topics))
    }

    var body: some View {
        let visiblePapers = viewModel.visiblePapers(personalStates: personalStates)
        ScrollView {
            LazyVStack(alignment: .leading, spacing: PFTheme.Spacing.medium) {
                controls
                Text("\(visiblePapers.count) papers")
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(PFTheme.textSecondary)
                    .monospacedDigit()
                    .accessibilityIdentifier("browse.paper.count")

                if visiblePapers.isEmpty {
                    PFEmptyShell(
                        title: "No matching papers",
                        message: "Adjust the local topic or review-state filters."
                    )
                } else {
                    ForEach(visiblePapers) { paper in
                        browseRow(paper)
                            .id(paper.arxivId)
                    }
                }
            }
            .padding(PFTheme.Spacing.standard)
        }
        .background(PFTheme.background)
        .navigationTitle(PFDateText.long(feed.date))
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button("Filter", systemImage: "line.3.horizontal.decrease") {
                    showsFilters = true
                }
                .accessibilityIdentifier("browse.filter")
            }
        }
        .sheet(isPresented: $showsFilters) { filterSheet }
        .alert("Personal state wasn’t updated", isPresented: .constant(actionError != nil)) {
            Button("OK") { actionError = nil }
        } message: {
            Text(actionError ?? "")
        }
        .accessibilityIdentifier("screen.day.browse")
    }

    private var controls: some View {
        HStack {
            Menu {
                ForEach(DayBrowseSort.allCases) { option in
                    Button {
                        viewModel.sort = option
                    } label: {
                        if viewModel.sort == option {
                            Label(option.rawValue, systemImage: "checkmark")
                        } else {
                            Text(option.rawValue)
                        }
                    }
                }
            } label: {
                Label("Sort: \(viewModel.sort.rawValue)", systemImage: "arrow.up.arrow.down")
            }
            .accessibilityIdentifier("browse.sort")
            Spacer()
            if viewModel.status != .all || !viewModel.selectedTopicIDs.isEmpty {
                Button("Reset") { viewModel.resetFilters() }
                    .accessibilityIdentifier("browse.reset")
            }
        }
        .buttonStyle(.bordered)
    }

    private func browseRow(_ paper: PublicPaper) -> some View {
        let state = personalState(for: paper)
        return VStack(alignment: .trailing, spacing: PFTheme.Spacing.small) {
            NavigationLink {
                PaperDetailView(paper: paper, topics: topics)
            } label: {
                PFPaperBrowseCard(
                    paper: paper,
                    topicLabels: Array(PaperDetailViewModel.topicLabels(for: paper, topics: topics).prefix(2)),
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
            .tint(state?.saved == true ? PFTheme.primary : PFTheme.textSecondary)
            .accessibilityIdentifier("paper.save.\(paper.arxivId)")
        }
    }

    private var filterSheet: some View {
        NavigationStack {
            Form {
                Section("Topics") {
                    Button("All Topics") { viewModel.selectedTopicIDs = [] }
                    ForEach(viewModel.availableTopics) { topic in
                        Button {
                            if viewModel.selectedTopicIDs.contains(topic.id) {
                                viewModel.selectedTopicIDs.remove(topic.id)
                            } else {
                                viewModel.selectedTopicIDs.insert(topic.id)
                            }
                        } label: {
                            HStack {
                                Text(topic.name)
                                Spacer()
                                if viewModel.selectedTopicIDs.contains(topic.id) {
                                    Image(systemName: "checkmark")
                                }
                            }
                        }
                    }
                }
                Section("Status") {
                    Picker("Status", selection: $viewModel.status) {
                        ForEach(DayBrowseStatus.allCases) { status in
                            Text(status.rawValue).tag(status)
                        }
                    }
                    .pickerStyle(.inline)
                }
            }
            .navigationTitle("Filters")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Reset") { viewModel.resetFilters() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Apply") { showsFilters = false }
                }
            }
        }
        .presentationDetents([.medium, .large])
    }

    private func personalState(for paper: PublicPaper) -> PersonalPaperState? {
        let id = PublicPaper.normalizeArxivID(paper.arxivId)
        return personalStates.first { $0.canonicalArxivID == id }
    }

    private func toggleSave(_ paper: PublicPaper, state: PersonalPaperState?) {
        do {
            let service = PersonalActionService(
                store: SwiftDataPersonalPaperStore(modelContext: modelContext)
            )
            if state?.saved == true {
                try service.unsave(arxivID: paper.arxivId)
            } else {
                try service.save(paper)
            }
        } catch {
            actionError = "Your previous personal state is unchanged."
        }
    }
}

struct PFPaperBrowseCard: View {
    let paper: PublicPaper
    let topicLabels: [String]
    let isReviewed: Bool
    let isSaved: Bool
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize

    var body: some View {
        Group {
            if dynamicTypeSize.isAccessibilitySize {
                VStack(alignment: .leading, spacing: PFTheme.Spacing.medium) {
                    PFFigurePlaceholder(status: paper.figureStatus, height: 150)
                    paperContent
                }
            } else {
                HStack(alignment: .top, spacing: PFTheme.Spacing.medium) {
                    PFFigurePlaceholder(status: paper.figureStatus, height: 108)
                        .frame(width: 116)
                    paperContent
                }
            }
        }
        .padding(PFTheme.Spacing.standard)
        .background(PFTheme.surface, in: .rect(cornerRadius: PFTheme.Radius.card))
        .overlay {
            RoundedRectangle(cornerRadius: PFTheme.Radius.card)
                .stroke(PFTheme.divider.opacity(0.5), lineWidth: 0.5)
        }
        .accessibilityElement(children: .combine)
        .accessibilityIdentifier("browse.paper.\(paper.arxivId)")
    }

    private var paperContent: some View {
        VStack(alignment: .leading, spacing: PFTheme.Spacing.small) {
                Text(paper.title)
                    .font(.headline)
                    .lineLimit(3)
                if !topicLabels.isEmpty {
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack { ForEach(topicLabels, id: \.self) { PFTag(text: $0) } }
                    }
                }
                Text(paper.displaySummary)
                    .font(.subheadline)
                    .foregroundStyle(PFTheme.textSecondary)
                    .lineLimit(3)
                HStack {
                    Text("Rel. \(paper.relevance)")
                    Text("Nov. \(paper.novelty)")
                    Spacer()
                    if isReviewed { Image(systemName: "checkmark.circle.fill") }
                    if isSaved { Image(systemName: "bookmark.fill") }
                }
                .font(.caption.weight(.semibold))
                .foregroundStyle(isReviewed ? PFTheme.success : PFTheme.textSecondary)
        }
    }
}
