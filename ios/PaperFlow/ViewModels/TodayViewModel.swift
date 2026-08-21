import Foundation

enum TodaySelection: Equatable {
    case current(FeedDay)
    case unavailable(latest: FeedDay?)
}

struct CollectionProgress: Equatable {
    let reviewed: Int
    let total: Int

    var remaining: Int { max(total - reviewed, 0) }
    var fraction: Double { total == 0 ? 0 : Double(reviewed) / Double(total) }
    var percentage: Int { Int((fraction * 100).rounded()) }
}

enum TodayViewModel {
    static func publicationDate(now: Date, timezoneID: String) throws -> Date {
        guard let timezone = TimeZone(identifier: timezoneID) else {
            throw PublicContractError.invalidIdentifier
        }
        var publicationCalendar = Calendar(identifier: .gregorian)
        publicationCalendar.timeZone = timezone
        let components = publicationCalendar.dateComponents([.year, .month, .day], from: now)
        var canonicalCalendar = Calendar(identifier: .gregorian)
        canonicalCalendar.timeZone = TimeZone(secondsFromGMT: 0)!
        guard let date = canonicalCalendar.date(from: components) else {
            throw PublicContractError.invalidIdentifier
        }
        return date
    }

    static func selection(for index: FeedIndex, now: Date) throws -> TodaySelection {
        let today = try publicationDate(now: now, timezoneID: index.timezone)
        if let current = index.days.first(where: { $0.date == today }) {
            return .current(current)
        }
        return .unavailable(latest: index.days.first)
    }

    static func previousDays(for index: FeedIndex, now: Date) throws -> [FeedDay] {
        let today = try publicationDate(now: now, timezoneID: index.timezone)
        return index.days.filter { $0.date != today }
    }

    static func progress(
        for feed: DailyFeed,
        personalStates: [PersonalPaperState]
    ) -> CollectionProgress {
        let reviewedIDs = Set(
            personalStates.lazy.filter(\.seen).map(\.canonicalArxivID)
        )
        let reviewed = feed.papers.reduce(into: 0) { count, paper in
            if reviewedIDs.contains(PublicPaper.normalizeArxivID(paper.arxivId)) {
                count += 1
            }
        }
        return CollectionProgress(reviewed: reviewed, total: feed.paperCount)
    }
}
