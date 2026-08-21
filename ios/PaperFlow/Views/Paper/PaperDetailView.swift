import SwiftData
import SwiftUI

struct PaperDetailView: View {
    let paper: PublicPaper
    let topics: TopicsIndex?
    var onSwipeSave: (() throws -> Void)? = nil
    var onSwipeSkip: (() throws -> Void)? = nil
    @Environment(\.modelContext) private var modelContext
    @Environment(\.openURL) private var openURL
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize
    @Environment(\.dismiss) private var dismiss
    @Environment(\.pfHaptics) private var haptics
    @Query private var personalStates: [PersonalPaperState]
    @State private var showsFullAbstract = false
    @State private var noteDraft = ""
    @State private var noteLoaded = false
    @State private var didMarkOpened = false
    @State private var actionError: String?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: PFTheme.Spacing.large) {
                PFFigurePlaceholder(status: paper.figureStatus, height: 210)
                titleSection
                scoreSection
                summarySection
                abstractSection
                whySelectedSection
                swipeDecisionSection
                personalSection
                externalActions
            }
            .padding(PFTheme.Spacing.standard)
        }
        .background(PFTheme.background)
        .navigationTitle("Paper Detail")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                ShareLink(item: paper.arxivUrl)
                    .accessibilityIdentifier("detail.share")
            }
        }
        .task { preparePresentation() }
        .onChange(of: noteDraft) { _, newValue in
            guard noteLoaded, currentState?.saved == true, newValue != currentState?.note else { return }
            perform { try actionService.updateNote(arxivID: paper.arxivId, note: newValue) }
        }
        .alert("Personal state wasn’t updated", isPresented: .constant(actionError != nil)) {
            Button("OK") { actionError = nil }
        } message: {
            Text(actionError ?? "")
        }
        .accessibilityIdentifier("screen.paper.detail")
    }

    private var titleSection: some View {
        VStack(alignment: .leading, spacing: PFTheme.Spacing.small) {
            Text(paper.title)
                .font(.title.bold())
                .fixedSize(horizontal: false, vertical: true)
            Text(paper.authors.joined(separator: ", "))
                .foregroundStyle(PFTheme.textSecondary)
            Text("arXiv:\(paper.arxivId)")
                .font(.caption)
                .foregroundStyle(PFTheme.textTertiary)
            let labels = PaperDetailViewModel.topicLabels(for: paper, topics: topics)
            if !labels.isEmpty {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack { ForEach(labels, id: \.self) { PFTag(text: $0) } }
                }
            }
        }
    }

    private var scoreSection: some View {
        Group {
            if dynamicTypeSize.isAccessibilitySize {
                VStack(spacing: PFTheme.Spacing.medium) {
                    scoreCard(title: "Relevance", value: paper.relevance)
                    scoreCard(title: "Novelty", value: paper.novelty)
                }
            } else {
                HStack(spacing: PFTheme.Spacing.medium) {
                    scoreCard(title: "Relevance", value: paper.relevance)
                    scoreCard(title: "Novelty", value: paper.novelty)
                }
            }
        }
    }

    @ViewBuilder
    private var summarySection: some View {
        switch PaperDetailViewModel.summary(for: paper) {
        case let .generated(tldr, bullets):
            detailSection("TL;DR") {
                Text(tldr).font(.body)
            }
            if !bullets.isEmpty {
                detailSection("Key Points") {
                    VStack(alignment: .leading, spacing: PFTheme.Spacing.small) {
                        ForEach(bullets, id: \.self) { Text("• \($0)") }
                    }
                }
            }
        case .abstractFallback:
            EmptyView()
        }
    }

    private var abstractSection: some View {
        detailSection("Abstract") {
            VStack(alignment: .leading, spacing: PFTheme.Spacing.small) {
                Text(paper.abstract)
                    .lineLimit(showsFullAbstract ? nil : 8)
                if paper.abstract.count > 500 {
                    Button(showsFullAbstract ? "Show Less" : "Show More") {
                        showsFullAbstract.toggle()
                    }
                }
            }
        }
    }

    private var whySelectedSection: some View {
        DisclosureGroup("Why Selected") {
            Text(paper.selectionReason)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.top, PFTheme.Spacing.small)
        }
        .font(.headline)
        .padding(PFTheme.Spacing.standard)
        .background(PFTheme.surface, in: .rect(cornerRadius: PFTheme.Radius.card))
    }

    @ViewBuilder
    private var swipeDecisionSection: some View {
        if let onSwipeSave, let onSwipeSkip {
            detailSection("Triage Decision") {
                HStack {
                    Button("Skip", systemImage: "xmark", role: .destructive) {
                        perform {
                            try onSwipeSkip()
                            dismiss()
                        }
                    }
                    .frame(maxWidth: .infinity, minHeight: PFTheme.minimumTapTarget)
                    .buttonStyle(.bordered)
                    .accessibilityIdentifier("detail.swipe.skip")
                    Button("Save", systemImage: "bookmark.fill") {
                        perform {
                            try onSwipeSave()
                            dismiss()
                        }
                    }
                    .frame(maxWidth: .infinity, minHeight: PFTheme.minimumTapTarget)
                    .buttonStyle(.borderedProminent)
                    .tint(PFTheme.success)
                    .accessibilityIdentifier("detail.swipe.save")
                }
            }
        }
    }

    @ViewBuilder
    private var personalSection: some View {
        detailSection("Personal State") {
            if let state = currentState, state.saved {
                PFReadingStatusPicker(status: state.readingStatus ?? .queue) { status in
                    perform {
                        try actionService.transition(arxivID: paper.arxivId, to: status)
                        if status == .done { haptics.trigger(.completedReading) }
                    }
                }
                .accessibilityIdentifier("detail.reading.status")

                PFNoteEditor(text: $noteDraft)
                    .accessibilityIdentifier("detail.notes")

                PFRatingControl(rating: state.rating) { rating in
                    perform { try actionService.updateRating(arxivID: paper.arxivId, rating: rating) }
                }

                Button("Remove from Saved", role: .destructive) {
                    perform { try actionService.unsave(arxivID: paper.arxivId) }
                }
                .accessibilityIdentifier("detail.unsave")
            } else if onSwipeSave == nil {
                PFPrimaryButton(
                    title: "Save for Deep Read",
                    systemImage: "bookmark",
                    accessibilityIdentifier: "detail.save"
                ) {
                    perform {
                        try actionService.save(paper)
                        haptics.trigger(.save)
                        try markOpenedIfNeeded()
                        noteDraft = currentState?.note ?? ""
                        noteLoaded = true
                    }
                }
            } else {
                Text("Choose Save above to add this paper to your deep-read queue.")
                    .foregroundStyle(PFTheme.textSecondary)
            }
        }
    }

    private var externalActions: some View {
        detailSection("External Actions") {
            Group {
                if dynamicTypeSize.isAccessibilitySize {
                    VStack {
                        externalButton("Open arXiv", image: "safari", url: paper.arxivUrl)
                        externalButton("Open PDF", image: "doc.fill", url: paper.pdfUrl)
                    }
                } else {
                    HStack {
                        externalButton("Open arXiv", image: "safari", url: paper.arxivUrl)
                        externalButton("Open PDF", image: "doc.fill", url: paper.pdfUrl)
                    }
                }
            }
        }
    }

    private var currentState: PersonalPaperState? {
        let id = PublicPaper.normalizeArxivID(paper.arxivId)
        return personalStates.first { $0.canonicalArxivID == id }
    }

    private var actionService: PersonalActionService {
        PersonalActionService(store: SwiftDataPersonalPaperStore(modelContext: modelContext))
    }

    private func preparePresentation() {
        noteDraft = currentState?.note ?? ""
        noteLoaded = true
        perform { try markOpenedIfNeeded() }
    }

    private func markOpenedIfNeeded() throws {
        guard !didMarkOpened, currentState?.saved == true else { return }
        try actionService.markOpened(arxivID: paper.arxivId)
        didMarkOpened = true
    }

    private func perform(_ operation: () throws -> Void) {
        do { try operation() } catch {
            actionError = "Your previous personal state is unchanged."
        }
    }

    private func open(_ url: URL) {
        perform { try actionService.markOpened(arxivID: paper.arxivId) }
        openURL(url)
    }

    private func externalButton(_ title: String, image: String, url: URL) -> some View {
        Button { open(url) } label: {
            Label(title, systemImage: image)
                .frame(maxWidth: .infinity, minHeight: PFTheme.minimumTapTarget)
        }
        .buttonStyle(.borderedProminent)
        .tint(title == "Open PDF" ? PFTheme.primary : PFTheme.textSecondary)
        .accessibilityIdentifier(title == "Open PDF" ? "detail.open.pdf" : "detail.open.arxiv")
    }

    private func scoreCard(title: String, value: Int) -> some View {
        VStack(alignment: .leading, spacing: PFTheme.Spacing.xSmall) {
            Text(title).font(.caption).foregroundStyle(PFTheme.textSecondary)
            Text("\(value) / 10").font(.headline).monospacedDigit()
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(PFTheme.Spacing.standard)
        .background(PFTheme.surface, in: .rect(cornerRadius: PFTheme.Radius.card))
    }

    private func detailSection<Content: View>(
        _ title: String,
        @ViewBuilder content: () -> Content
    ) -> some View {
        VStack(alignment: .leading, spacing: PFTheme.Spacing.medium) {
            Text(title).font(.headline)
            content()
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(PFTheme.Spacing.standard)
        .background(PFTheme.surface, in: .rect(cornerRadius: PFTheme.Radius.card))
    }
}
