import SwiftData
import SwiftUI

struct TodayHomeView: View {
    @Bindable var model: AppModel
    @Query private var personalStates: [PersonalPaperState]
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: PFTheme.Spacing.large) {
                header
                stateContent
            }
            .padding(PFTheme.Spacing.standard)
        }
        .background(PFTheme.background)
        .navigationBarTitleDisplayMode(.inline)
        .refreshable { await model.refresh() }
        .accessibilityIdentifier("screen.today")
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: PFTheme.Spacing.xSmall) {
            PFBrandMark()
                .padding(.bottom, PFTheme.Spacing.small)
            Text("Today")
                .font(.largeTitle.bold())
            Text(model.currentDate.formatted(.dateTime.weekday(.wide).month(.abbreviated).day()))
                .font(.subheadline)
                .foregroundStyle(PFTheme.textSecondary)
        }
    }

    @ViewBuilder
    private var stateContent: some View {
        switch model.loadState {
        case .idle, .loading:
            PFLoadingShell()
        case let .failed(message):
            PFErrorShell(message: message) { Task { await model.refresh() } }
        case .loaded:
            if let index = model.feedIndex {
                loadedContent(index)
            } else {
                PFErrorShell(message: "The PaperFlow day index is unavailable.")
            }
        }
    }

    @ViewBuilder
    private func loadedContent(_ index: FeedIndex) -> some View {
        if model.isShowingCachedData {
            PFOfflineIndicator(lastUpdatedAt: model.lastUpdatedAt)
        }
        if let message = model.refreshMessage {
            PFErrorBanner(message: message) { Task { await model.refresh() } }
        }

        let selection = try? TodayViewModel.selection(for: index, now: model.currentDate)
        switch selection {
        case let .current(day):
            dayCard(day, title: "Today’s Papers", zeroDayIsToday: true)
        case let .unavailable(latest):
            PFEmptyShell(
                title: "Today’s feed isn’t available yet",
                message: "The newest successful PaperFlow day is shown below."
            )
            if let latest {
                Text("Latest Available")
                    .font(.headline)
                dayCard(latest, title: PFDateText.short(latest.date), zeroDayIsToday: false)
            }
        case nil:
            PFErrorShell(message: "The publication timezone is invalid.")
        }

        let previous = displayPreviousDays(index: index, selection: selection)
        if !previous.isEmpty {
            PFSectionHeader(title: "Previous Days", count: previous.count)
            LazyVStack(spacing: PFTheme.Spacing.small) {
                ForEach(previous) { day in
                    NavigationLink {
                        DayOverviewView(model: model, day: day)
                    } label: {
                        previousDayRow(day)
                    }
                    .buttonStyle(.plain)
                    .accessibilityIdentifier("today.day.\(PFDateText.identifier(day.date))")
                }
            }
        }
    }

    private func displayPreviousDays(
        index: FeedIndex,
        selection: TodaySelection?
    ) -> [FeedDay] {
        let days = (try? TodayViewModel.previousDays(for: index, now: model.currentDate)) ?? []
        guard case let .some(.unavailable(latest)) = selection, let latest else {
            return days
        }
        return days.filter { $0.date != latest.date }
    }

    @ViewBuilder
    private func dayCard(_ day: FeedDay, title: String, zeroDayIsToday: Bool) -> some View {
        if let feed = model.dayFeeds[day.date] {
            let progress = TodayViewModel.progress(for: feed, personalStates: personalStates)
            VStack(alignment: .leading, spacing: PFTheme.Spacing.standard) {
                NavigationLink {
                    DayOverviewView(model: model, day: day)
                } label: {
                    if dynamicTypeSize.isAccessibilitySize {
                        VStack(alignment: .leading, spacing: PFTheme.Spacing.small) {
                            Text(title).font(.headline)
                            HStack {
                                Text(PFAccessibility.paperCount(day.paperCount)).monospacedDigit()
                                Image(systemName: "chevron.right")
                            }
                        }
                    } else {
                        HStack {
                            Text(title).font(.headline)
                            Spacer()
                            Text("\(day.paperCount) papers").monospacedDigit()
                            Image(systemName: "chevron.right")
                        }
                    }
                }
                .buttonStyle(.plain)

                if feed.paperCount == 0, zeroDayIsToday {
                    Text("No papers matched your research interests today.")
                        .foregroundStyle(PFTheme.textSecondary)
                } else {
                    progressSummary(progress)
                    Group {
                        if dynamicTypeSize.isAccessibilitySize {
                            VStack { dayActions(feed) }
                        } else {
                            HStack { dayActions(feed) }
                        }
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(PFTheme.primary)
                }
            }
            .padding(PFTheme.Spacing.standard)
            .background(PFTheme.surface, in: .rect(cornerRadius: PFTheme.Radius.feature))
        } else if let error = model.dayErrors[day.date] {
            PFErrorShell(message: error)
        } else {
            PFLoadingShell()
                .task { await model.loadDay(day) }
        }
    }

    @ViewBuilder
    private func dayActions(_ feed: DailyFeed) -> some View {
        NavigationLink {
            DayBrowseView(feed: feed, topics: model.topicsIndex)
        } label: {
            Label("Browse", systemImage: "list.bullet")
                .font(.headline)
                .frame(maxWidth: .infinity, minHeight: PFTheme.minimumTapTarget)
        }
        .accessibilityIdentifier("today.browse")
        NavigationLink {
            DaySwipeView(feed: feed, topics: model.topicsIndex)
        } label: {
            Label("Swipe", systemImage: "rectangle.stack")
                .font(.headline)
                .frame(maxWidth: .infinity, minHeight: PFTheme.minimumTapTarget)
        }
        .accessibilityIdentifier("today.swipe")
    }

    @ViewBuilder
    private func progressSummary(_ progress: CollectionProgress) -> some View {
        if dynamicTypeSize.isAccessibilitySize {
            VStack(alignment: .leading, spacing: PFTheme.Spacing.medium) {
                PFCircularProgress(progress: progress)
                Text("\(progress.reviewed) reviewed")
                Text("\(progress.remaining) remaining")
                    .foregroundStyle(PFTheme.textSecondary)
            }
            .monospacedDigit()
        } else {
            HStack(spacing: PFTheme.Spacing.large) {
                PFCircularProgress(progress: progress)
                VStack(alignment: .leading, spacing: PFTheme.Spacing.small) {
                    Text("\(progress.reviewed) reviewed")
                    Text("\(progress.remaining) remaining")
                        .foregroundStyle(PFTheme.textSecondary)
                }
                .monospacedDigit()
            }
        }
    }

    private func previousDayRow(_ day: FeedDay) -> some View {
        HStack(spacing: PFTheme.Spacing.medium) {
            Image(systemName: "calendar")
                .foregroundStyle(PFTheme.primary)
                .frame(width: PFTheme.minimumTapTarget)
            VStack(alignment: .leading, spacing: PFTheme.Spacing.xSmall) {
                Text(PFDateText.short(day.date)).font(.headline)
                Text("\(day.paperCount) papers")
                    .font(.caption)
                    .foregroundStyle(PFTheme.textSecondary)
            }
            Spacer()
            Image(systemName: "chevron.right")
                .foregroundStyle(PFTheme.textTertiary)
        }
        .frame(minHeight: 56)
        .padding(.horizontal, PFTheme.Spacing.standard)
        .background(PFTheme.surface, in: .rect(cornerRadius: PFTheme.Radius.card))
    }
}

enum PFDateText {
    private static let shortFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.locale = .autoupdatingCurrent
        formatter.timeZone = TimeZone(secondsFromGMT: 0)
        formatter.setLocalizedDateFormatFromTemplate("EEE MMM d")
        return formatter
    }()

    private static let longFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.locale = .autoupdatingCurrent
        formatter.timeZone = TimeZone(secondsFromGMT: 0)
        formatter.setLocalizedDateFormatFromTemplate("MMM d yyyy")
        return formatter
    }()

    private static let identifierFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(secondsFromGMT: 0)
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter
    }()

    static func short(_ date: Date) -> String { shortFormatter.string(from: date) }
    static func long(_ date: Date) -> String { longFormatter.string(from: date) }
    static func identifier(_ date: Date) -> String { identifierFormatter.string(from: date) }
}
