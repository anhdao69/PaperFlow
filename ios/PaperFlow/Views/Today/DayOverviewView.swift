import SwiftData
import SwiftUI

struct DayOverviewView: View {
    @Bindable var model: AppModel
    let day: FeedDay
    @Query private var personalStates: [PersonalPaperState]
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: PFTheme.Spacing.large) {
                if let feed = model.dayFeeds[day.date] {
                    let progress = TodayViewModel.progress(for: feed, personalStates: personalStates)
                    Group {
                        if dynamicTypeSize.isAccessibilitySize {
                            VStack(alignment: .leading, spacing: PFTheme.Spacing.medium) {
                                PFCircularProgress(progress: progress)
                                progressLabels(progress)
                            }
                        } else {
                            HStack(spacing: PFTheme.Spacing.large) {
                                PFCircularProgress(progress: progress)
                                progressLabels(progress)
                            }
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(PFTheme.Spacing.large)
                    .background(PFTheme.surface, in: .rect(cornerRadius: PFTheme.Radius.feature))

                    if feed.paperCount == 0 {
                        PFEmptyShell(
                            title: "No papers",
                            message: "No papers matched the configured research interests for this day."
                        )
                    } else {
                        NavigationLink {
                            DayBrowseView(feed: feed, topics: model.topicsIndex)
                        } label: {
                            Label("Browse", systemImage: "list.bullet")
                                .font(.headline)
                                .frame(maxWidth: .infinity, minHeight: PFTheme.minimumTapTarget)
                        }
                        .buttonStyle(.borderedProminent)
                        .tint(PFTheme.primary)
                        .accessibilityIdentifier("day.overview.browse")
                    }
                } else if let error = model.dayErrors[day.date] {
                    PFErrorShell(message: error)
                } else {
                    PFLoadingShell()
                }
            }
            .padding(PFTheme.Spacing.standard)
        }
        .background(PFTheme.background)
        .navigationTitle(PFDateText.long(day.date))
        .navigationBarTitleDisplayMode(.inline)
        .task { await model.loadDay(day) }
        .accessibilityIdentifier("screen.day.overview")
    }

    private func progressLabels(_ progress: CollectionProgress) -> some View {
        VStack(alignment: .leading, spacing: PFTheme.Spacing.small) {
            Text("\(progress.reviewed) reviewed")
            Text("\(progress.remaining) remaining")
            Text("\(progress.total) papers")
                .foregroundStyle(PFTheme.textSecondary)
        }
        .font(.headline)
        .monospacedDigit()
    }
}
