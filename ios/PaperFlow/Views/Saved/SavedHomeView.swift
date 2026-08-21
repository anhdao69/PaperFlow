import SwiftData
import SwiftUI

struct SavedHomeView: View {
    @Bindable var model: AppModel
    let exploreToday: () -> Void
    @Query private var personalStates: [PersonalPaperState]
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize

    var body: some View {
        let counts = SavedViewModel.counts(personalStates)
        ScrollView {
            VStack(alignment: .leading, spacing: PFTheme.Spacing.large) {
                VStack(alignment: .leading, spacing: PFTheme.Spacing.small) {
                    Text("Saved")
                        .font(.largeTitle.bold())
                    Text("Your deep-read queue and progress.")
                        .foregroundStyle(PFTheme.textSecondary)
                }

                if counts.total == 0 {
                    VStack(spacing: PFTheme.Spacing.standard) {
                        PFEmptyShell(
                            title: "Nothing saved yet",
                            message: "Swipe right or tap Save on a paper you want to read later."
                        )
                        PFPrimaryButton(
                            title: "Explore Today",
                            systemImage: "calendar",
                            accessibilityIdentifier: "saved.explore.today",
                            action: exploreToday
                        )
                    }
                } else {
                    Text("Library Status")
                        .font(.headline)
                    Group {
                        if dynamicTypeSize.isAccessibilitySize {
                            VStack(spacing: PFTheme.Spacing.medium) { statusLinks(counts) }
                        } else {
                            HStack(spacing: PFTheme.Spacing.medium) { statusLinks(counts) }
                        }
                    }
                }
            }
            .padding(PFTheme.Spacing.standard)
        }
        .background(PFTheme.background)
        .navigationBarTitleDisplayMode(.inline)
        .accessibilityIdentifier("screen.saved")
    }

    @ViewBuilder
    private func statusLinks(_ counts: SavedCounts) -> some View {
        statusLink(.queue, count: counts.queue, subtitle: "Papers to read", tint: PFTheme.primary)
        statusLink(.reading, count: counts.reading, subtitle: "In progress", tint: PFTheme.warning)
        statusLink(.done, count: counts.done, subtitle: "Completed", tint: PFTheme.success)
    }

    private func statusLink(
        _ status: ReadingStatus,
        count: Int,
        subtitle: String,
        tint: Color
    ) -> some View {
        NavigationLink {
            destination(status)
        } label: {
            VStack(alignment: .leading, spacing: PFTheme.Spacing.small) {
                Label(status.displayName, systemImage: status.systemImage)
                    .font(.headline)
                    .foregroundStyle(tint)
                    .lineLimit(1)
                    .minimumScaleFactor(0.7)
                Text("\(count)")
                    .font(.title.bold())
                    .foregroundStyle(PFTheme.textPrimary)
                    .monospacedDigit()
                Text(subtitle)
                    .font(.caption)
                    .foregroundStyle(PFTheme.textSecondary)
                    .lineLimit(1)
                    .minimumScaleFactor(0.75)
            }
            .frame(maxWidth: .infinity, minHeight: 120, alignment: .leading)
            .padding(PFTheme.Spacing.standard)
            .background(PFTheme.surface, in: .rect(cornerRadius: PFTheme.Radius.card))
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier("saved.open.\(status.rawValue)")
    }

    @ViewBuilder
    private func destination(_ status: ReadingStatus) -> some View {
        switch status {
        case .queue: QueueView(model: model)
        case .reading: ReadingView(model: model)
        case .done: DoneView(model: model)
        }
    }
}
