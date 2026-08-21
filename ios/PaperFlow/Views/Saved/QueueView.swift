import SwiftData
import SwiftUI

struct QueueView: View {
    @Bindable var model: AppModel

    var body: some View {
        SavedCollectionView(model: model, status: .queue)
    }
}

struct SavedCollectionView: View {
    @Bindable var model: AppModel
    let status: ReadingStatus
    @Query private var personalStates: [PersonalPaperState]
    @Environment(\.modelContext) private var modelContext
    @State private var searchText = ""
    @State private var sort: SavedSort
    @State private var pendingUnsaveID: String?
    @State private var actionError: String?

    init(model: AppModel, status: ReadingStatus) {
        self.model = model
        self.status = status
        _sort = State(initialValue: SavedSort.defaultSort(for: status))
    }

    var body: some View {
        let records = SavedViewModel.records(
            personalStates,
            status: status,
            query: searchText,
            sort: sort,
            topics: model.topicsIndex
        )
        ScrollView {
            LazyVStack(alignment: .leading, spacing: PFTheme.Spacing.medium) {
                HStack {
                    Text("\(records.count) \(records.count == 1 ? "paper" : "papers")")
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(PFTheme.textSecondary)
                        .monospacedDigit()
                        .accessibilityIdentifier("saved.collection.count")
                    Spacer()
                    sortMenu
                }

                if records.isEmpty {
                    emptyState
                } else {
                    ForEach(records, id: \.canonicalArxivID) { state in
                        savedRow(state)
                    }
                }
            }
            .padding(PFTheme.Spacing.standard)
        }
        .background(PFTheme.background)
        .navigationTitle(status.displayName)
        .navigationBarTitleDisplayMode(.large)
        .searchable(
            text: $searchText,
            placement: .navigationBarDrawer(displayMode: .always),
            prompt: "Search Saved"
        )
        .confirmationDialog(
            "Remove from Saved?",
            isPresented: Binding(
                get: { pendingUnsaveID != nil },
                set: { if !$0 { pendingUnsaveID = nil } }
            ),
            titleVisibility: .visible
        ) {
            Button("Remove from Saved", role: .destructive) {
                if let id = pendingUnsaveID { perform { try actionService.unsave(arxivID: id) } }
                pendingUnsaveID = nil
            }
            Button("Cancel", role: .cancel) { pendingUnsaveID = nil }
        } message: {
            Text("Your review history, note, rating, reading state, and offline snapshot will be kept.")
        }
        .alert("Personal state wasn’t updated", isPresented: .constant(actionError != nil)) {
            Button("OK") { actionError = nil }
        } message: {
            Text(actionError ?? "")
        }
        .accessibilityIdentifier("screen.saved.\(status.rawValue)")
    }

    private var sortMenu: some View {
        Menu {
            ForEach(SavedSort.options(for: status)) { option in
                Button {
                    sort = option
                } label: {
                    if sort == option {
                        Label(option.rawValue, systemImage: "checkmark")
                    } else {
                        Text(option.rawValue)
                    }
                }
            }
        } label: {
            Label("Sort: \(sort.rawValue)", systemImage: "arrow.up.arrow.down")
        }
        .buttonStyle(.bordered)
        .accessibilityIdentifier("saved.sort")
    }

    private func savedRow(_ state: PersonalPaperState) -> some View {
        VStack(alignment: .trailing, spacing: PFTheme.Spacing.small) {
            if let snapshot = state.snapshot {
                NavigationLink {
                    PaperDetailView(paper: snapshot.publicPaper(), topics: model.topicsIndex)
                } label: {
                    PFSavedPaperRow(state: state, topics: model.topicsIndex)
                }
                .buttonStyle(.plain)
            }
            HStack {
                Menu {
                    ForEach(ReadingStatus.allCases, id: \.self) { option in
                        Button {
                            perform { try actionService.transition(arxivID: state.canonicalArxivID, to: option) }
                        } label: {
                            if option == (state.readingStatus ?? .queue) {
                                Label(option.displayName, systemImage: "checkmark")
                            } else {
                                Text(option.displayName)
                            }
                        }
                    }
                } label: {
                    Label(state.readingStatus?.displayName ?? "Queue", systemImage: "arrow.triangle.2.circlepath")
                }
                .accessibilityIdentifier("saved.status.\(state.canonicalArxivID)")
                Spacer()
                Button("Unsave", systemImage: "bookmark.slash", role: .destructive) {
                    pendingUnsaveID = state.canonicalArxivID
                }
                .accessibilityIdentifier("saved.unsave.\(state.canonicalArxivID)")
            }
            .buttonStyle(.bordered)
        }
        .contextMenu {
            ForEach(ReadingStatus.allCases, id: \.self) { option in
                Button("Mark \(option.displayName)") {
                    perform { try actionService.transition(arxivID: state.canonicalArxivID, to: option) }
                }
            }
            Button("Remove from Saved", role: .destructive) {
                pendingUnsaveID = state.canonicalArxivID
            }
        }
    }

    private var emptyState: some View {
        Group {
            if !searchText.isEmpty {
                PFEmptyShell(title: "No matches", message: "Try another Saved search.")
            } else {
                switch status {
                case .queue:
                    PFEmptyShell(
                        title: "Your queue is clear",
                        message: "Saved papers marked for later reading will appear here."
                    )
                case .reading:
                    PFEmptyShell(
                        title: "Nothing in progress",
                        message: "Move a saved paper to Reading when you start digging in."
                    )
                case .done:
                    PFEmptyShell(title: "No completed papers yet", message: "Finished papers will appear here.")
                }
            }
        }
    }

    private var actionService: PersonalActionService {
        PersonalActionService(store: SwiftDataPersonalPaperStore(modelContext: modelContext))
    }

    private func perform(_ operation: () throws -> Void) {
        do { try operation() } catch { actionError = "Your previous personal state is unchanged." }
    }
}
