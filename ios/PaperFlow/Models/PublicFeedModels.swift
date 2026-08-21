import Foundation

enum PublicContractError: Error, Equatable {
    case unsupportedSchema(Int)
    case invalidCount
    case invalidOrder
    case invalidIdentifier
    case invalidRelativePath
    case invalidAbsoluteURL
    case invalidSummary
    case invalidFigure
}

enum SummaryStatus: String, Codable, Sendable {
    case pending
    case generated
    case failed
}

enum FigureStatus: String, Codable, Sendable {
    case notImplemented = "not_implemented"
    case ready
    case failed
}

struct TopicAssignment: Codable, Hashable, Sendable {
    let topicId: String
    let subtopicIds: [String]
}

struct PublicPaper: Codable, Hashable, Identifiable, Sendable {
    var id: String { arxivId }
    let arxivId: String
    let title: String
    let authors: [String]
    let abstract: String
    let arxivUrl: URL
    let pdfUrl: URL
    let firstSeenAt: Date
    let categories: [String]
    let relevance: Int
    let novelty: Int
    let topicAssignments: [TopicAssignment]
    let selectionReason: String
    let tldr: String?
    let bullets: [String]
    let summaryStatus: SummaryStatus
    let heroFigure: String?
    let figureStatus: FigureStatus

    var displaySummary: String { tldr ?? abstract }

    func validated() throws -> Self {
        guard Self.normalizeArxivID(arxivId) == arxivId else {
            throw PublicContractError.invalidIdentifier
        }
        guard arxivUrl.scheme == "https", pdfUrl.scheme == "https" else {
            throw PublicContractError.invalidAbsoluteURL
        }
        guard (1 ... 10).contains(relevance), (1 ... 10).contains(novelty) else {
            throw PublicContractError.invalidCount
        }
        if summaryStatus == .generated {
            guard let tldr, !tldr.isEmpty, (3 ... 5).contains(bullets.count) else {
                throw PublicContractError.invalidSummary
            }
        } else if tldr != nil || !bullets.isEmpty {
            throw PublicContractError.invalidSummary
        }
        if figureStatus == .ready {
            guard let heroFigure else { throw PublicContractError.invalidFigure }
            _ = try PublicationURLResolver.validateRelativePath(heroFigure)
        } else if heroFigure != nil {
            throw PublicContractError.invalidFigure
        }
        return self
    }

    static func normalizeArxivID(_ value: String) -> String {
        value.replacingOccurrences(
            of: #"v\d+$"#,
            with: "",
            options: .regularExpression
        )
    }
}

struct FeedDay: Codable, Hashable, Identifiable, Sendable {
    var id: Date { date }
    let date: Date
    let paperCount: Int
    let feedUrl: String
}

struct FeedIndex: Codable, Hashable, Sendable {
    let schemaVersion: Int
    let generatedAt: Date
    let timezone: String
    let totalPaperCount: Int
    let dayCount: Int
    let days: [FeedDay]

    func validated() throws -> Self {
        guard schemaVersion == 1 else {
            throw PublicContractError.unsupportedSchema(schemaVersion)
        }
        guard TimeZone(identifier: timezone) != nil else {
            throw PublicContractError.invalidIdentifier
        }
        guard dayCount == days.count,
              totalPaperCount == days.reduce(0, { $0 + $1.paperCount }) else {
            throw PublicContractError.invalidCount
        }
        guard days.map(\.date) == days.map(\.date).sorted(by: >),
              Set(days.map(\.date)).count == days.count else {
            throw PublicContractError.invalidOrder
        }
        for day in days {
            _ = try PublicationURLResolver.validateRelativePath(day.feedUrl)
        }
        return self
    }
}

struct DailyFeed: Codable, Hashable, Sendable {
    let schemaVersion: Int
    let date: Date
    let paperCount: Int
    let papers: [PublicPaper]

    func validated() throws -> Self {
        guard schemaVersion == 1 else {
            throw PublicContractError.unsupportedSchema(schemaVersion)
        }
        guard paperCount == papers.count else {
            throw PublicContractError.invalidCount
        }
        for paper in papers { _ = try paper.validated() }
        return self
    }
}

struct PublicSubtopic: Codable, Hashable, Identifiable, Sendable {
    let id: String
    let name: String
    let paperCount: Int
    let feedUrl: String
}

struct PublicTopic: Codable, Hashable, Identifiable, Sendable {
    let id: String
    let name: String
    let paperCount: Int
    let feedUrl: String
    let subtopics: [PublicSubtopic]
}

struct TopicsIndex: Codable, Hashable, Sendable {
    let schemaVersion: Int
    let taxonomyVersion: Int
    let totalPaperCount: Int
    let topics: [PublicTopic]

    func validated() throws -> Self {
        guard schemaVersion == 1 else {
            throw PublicContractError.unsupportedSchema(schemaVersion)
        }
        guard Set(topics.map(\.id)).count == topics.count else {
            throw PublicContractError.invalidIdentifier
        }
        for topic in topics {
            _ = try PublicationURLResolver.validateRelativePath(topic.feedUrl)
            guard Set(topic.subtopics.map(\.id)).count == topic.subtopics.count else {
                throw PublicContractError.invalidIdentifier
            }
            for subtopic in topic.subtopics {
                _ = try PublicationURLResolver.validateRelativePath(subtopic.feedUrl)
            }
        }
        return self
    }
}

struct TopicFeedDay: Codable, Hashable, Identifiable, Sendable {
    var id: Date { date }
    let date: Date
    let paperCount: Int
    let papers: [PublicPaper]
}

struct TopicFeed: Codable, Hashable, Sendable {
    let schemaVersion: Int
    let topicId: String
    let subtopicId: String?
    let totalPaperCount: Int
    let days: [TopicFeedDay]

    func validated() throws -> Self {
        guard schemaVersion == 1 else {
            throw PublicContractError.unsupportedSchema(schemaVersion)
        }
        guard totalPaperCount == days.reduce(0, { $0 + $1.paperCount }),
              days.allSatisfy({ $0.paperCount == $0.papers.count }) else {
            throw PublicContractError.invalidCount
        }
        guard days.map(\.date) == days.map(\.date).sorted(by: >),
              Set(days.map(\.date)).count == days.count else {
            throw PublicContractError.invalidOrder
        }
        let papers = days.flatMap(\.papers)
        guard Set(papers.map(\.arxivId)).count == papers.count else {
            throw PublicContractError.invalidIdentifier
        }
        for paper in papers { _ = try paper.validated() }
        return self
    }
}

enum PublicFeedDecoder {
    static func decode<T: Decodable>(_ type: T.Type, from data: Data) throws -> T {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        decoder.dateDecodingStrategy = .custom { decoder in
            let container = try decoder.singleValueContainer()
            let value = try container.decode(String.self)
            if let day = Self.dayFormatter.date(from: value) { return day }
            if let instant = Self.fractionalInstantFormatter.date(from: value) {
                return instant
            }
            if let instant = Self.instantFormatter.date(from: value) { return instant }
            throw DecodingError.dataCorruptedError(
                in: container,
                debugDescription: "Expected ISO-8601 date or timestamp."
            )
        }
        return try decoder.decode(type, from: data)
    }

    private static let dayFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.calendar = Calendar(identifier: .gregorian)
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(secondsFromGMT: 0)
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter
    }()

    private static let instantFormatter = ISO8601DateFormatter()

    private static let fractionalInstantFormatter: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions.insert(.withFractionalSeconds)
        return formatter
    }()
}

enum PublicFeedEncoder {
    static func encode<T: Encodable>(_ value: T) throws -> Data {
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        encoder.dateEncodingStrategy = .iso8601
        encoder.outputFormatting = [.sortedKeys]
        return try encoder.encode(value)
    }
}

enum PublicationURLResolver {
    static func validateRelativePath(_ path: String) throws -> String {
        guard !path.isEmpty,
              !path.hasPrefix("/"),
              !path.contains("\\"),
              !path.contains(".."),
              !path.contains("?"),
              !path.contains("#"),
              URL(string: path)?.scheme == nil else {
            throw PublicContractError.invalidRelativePath
        }
        return path
    }

    static func resolve(_ path: String, against baseURL: URL) throws -> URL {
        _ = try validateRelativePath(path)
        guard baseURL.scheme == "https", baseURL.absoluteString.hasSuffix("/"),
              let resolved = URL(string: path, relativeTo: baseURL)?.absoluteURL else {
            throw PublicContractError.invalidAbsoluteURL
        }
        return resolved
    }
}
