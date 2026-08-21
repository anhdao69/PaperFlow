import SwiftUI

struct PFSectionHeader: View {
    let title: String
    var count: Int?

    var body: some View {
        HStack {
            Text(title)
                .font(.headline)
            Spacer()
            if let count {
                Text("\(count)")
                    .foregroundStyle(PFTheme.textSecondary)
                    .monospacedDigit()
            }
        }
        .accessibilityElement(children: .combine)
    }
}

struct PFPrimaryButton: View {
    let title: String
    let systemImage: String
    let accessibilityIdentifier: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Label(title, systemImage: systemImage)
                .font(.headline)
                .frame(maxWidth: .infinity, minHeight: PFTheme.minimumTapTarget)
        }
        .buttonStyle(.borderedProminent)
        .tint(PFTheme.primary)
        .clipShape(.rect(cornerRadius: PFTheme.Radius.control))
        .accessibilityIdentifier(accessibilityIdentifier)
    }
}

struct PFTag: View {
    let text: String

    var body: some View {
        Text(text)
            .font(.caption.weight(.semibold))
            .foregroundStyle(PFTheme.primary)
            .padding(.horizontal, PFTheme.Spacing.small)
            .padding(.vertical, PFTheme.Spacing.xSmall)
            .background(PFTheme.primarySoft, in: .rect(cornerRadius: PFTheme.Radius.tag))
    }
}

struct PFProgressView: View {
    let reviewed: Int
    let total: Int

    var body: some View {
        VStack(alignment: .leading, spacing: PFTheme.Spacing.small) {
            ProgressView(value: Double(reviewed), total: Double(max(total, 1)))
                .tint(PFTheme.primary)
            Text("\(reviewed) of \(total) papers reviewed")
                .font(.caption)
                .foregroundStyle(PFTheme.textSecondary)
        }
        .accessibilityElement(children: .combine)
        .accessibilityValue(PFAccessibility.progress(reviewed: reviewed, total: total))
    }
}

struct PFFigurePlaceholder: View {
    let status: FigureStatus
    var height: CGFloat = 132

    var body: some View {
        ZStack {
            PFTheme.primarySoft
            VStack(spacing: PFTheme.Spacing.small) {
                Image(systemName: "doc.richtext")
                    .font(.title)
                    .foregroundStyle(PFTheme.primary)
                Text(status == .failed ? "Figure unavailable" : "Figure preview")
                    .font(.caption)
                    .foregroundStyle(PFTheme.textSecondary)
            }
        }
        .frame(height: height)
        .clipShape(.rect(cornerRadius: PFTheme.Radius.card))
        .accessibilityLabel(status == .failed ? "Figure unavailable" : "Figure placeholder")
    }
}

struct PFCircularProgress: View {
    let progress: CollectionProgress
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize

    var body: some View {
        ZStack {
            Circle()
                .stroke(PFTheme.primarySoft, lineWidth: 9)
            Circle()
                .trim(from: 0, to: progress.fraction)
                .stroke(PFTheme.primary, style: StrokeStyle(lineWidth: 9, lineCap: .round))
                .rotationEffect(.degrees(-90))
            Text("\(progress.percentage)%")
                .font(.title3.bold())
                .monospacedDigit()
                .lineLimit(1)
                .minimumScaleFactor(0.45)
        }
        .frame(
            width: dynamicTypeSize.isAccessibilitySize ? 112 : 78,
            height: dynamicTypeSize.isAccessibilitySize ? 112 : 78
        )
        .accessibilityLabel("Review progress")
        .accessibilityValue("\(progress.reviewed) of \(progress.total) papers reviewed")
    }
}

struct PFPaperListCard: View {
    let paper: PublicPaper

    var body: some View {
        VStack(alignment: .leading, spacing: PFTheme.Spacing.medium) {
            PFFigurePlaceholder(status: paper.figureStatus)
            Text(paper.title)
                .font(.headline)
                .lineLimit(3)
            Text(paper.displaySummary)
                .font(.subheadline)
                .foregroundStyle(PFTheme.textSecondary)
                .lineLimit(4)
            HStack {
                PFTag(text: "Rel. \(paper.relevance)")
                PFTag(text: "Nov. \(paper.novelty)")
            }
        }
        .padding(PFTheme.Spacing.standard)
        .background(PFTheme.surface, in: .rect(cornerRadius: PFTheme.Radius.card))
        .overlay {
            RoundedRectangle(cornerRadius: PFTheme.Radius.card)
                .stroke(PFTheme.divider.opacity(0.5), lineWidth: 0.5)
        }
        .accessibilityElement(children: .combine)
        .accessibilityIdentifier("paper.card.\(paper.arxivId)")
    }
}

struct PFLoadingShell: View {
    var body: some View {
        PFLoadingSkeleton()
    }
}

struct PFLoadingSkeleton: View {
    var body: some View {
        VStack(alignment: .leading, spacing: PFTheme.Spacing.medium) {
            RoundedRectangle(cornerRadius: PFTheme.Radius.control)
                .fill(PFTheme.surfaceSecondary)
                .frame(height: 22)
                .frame(maxWidth: 180)
            RoundedRectangle(cornerRadius: PFTheme.Radius.card)
                .fill(PFTheme.surface)
                .frame(height: 150)
            ProgressView("Loading PaperFlow…")
                .foregroundStyle(PFTheme.textSecondary)
        }
        .frame(maxWidth: .infinity, minHeight: 180, alignment: .topLeading)
        .accessibilityElement(children: .combine)
        .accessibilityIdentifier("state.loading")
    }
}

struct PFEmptyShell: View {
    let title: String
    let message: String

    var body: some View {
        ContentUnavailableView(title, systemImage: "doc.text", description: Text(message))
            .accessibilityIdentifier("state.empty")
    }
}

struct PFErrorShell: View {
    let message: String
    var retry: (() -> Void)? = nil

    var body: some View {
        VStack(spacing: PFTheme.Spacing.standard) {
            ContentUnavailableView(
                "Unable to Load",
                systemImage: "exclamationmark.triangle",
                description: Text(message)
            )
            if let retry {
                Button("Try Again", systemImage: "arrow.clockwise", action: retry)
                    .buttonStyle(.borderedProminent)
                    .frame(minHeight: PFTheme.minimumTapTarget)
                    .accessibilityIdentifier("state.retry")
            }
        }
        .accessibilityIdentifier("state.error")
    }
}

struct PFErrorBanner: View {
    let message: String
    let retry: () -> Void

    var body: some View {
        HStack(alignment: .top, spacing: PFTheme.Spacing.medium) {
            Image(systemName: "exclamationmark.triangle.fill")
                .foregroundStyle(PFTheme.warning)
            VStack(alignment: .leading, spacing: PFTheme.Spacing.small) {
                Text(message)
                    .font(.subheadline)
                Button("Try Again", systemImage: "arrow.clockwise", action: retry)
                    .frame(minHeight: PFTheme.minimumTapTarget)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(PFTheme.Spacing.standard)
        .background(PFTheme.surface, in: .rect(cornerRadius: PFTheme.Radius.card))
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("state.error.banner")
    }
}

struct PFOfflineIndicator: View {
    let lastUpdatedAt: Date?

    var body: some View {
        Label(label, systemImage: "wifi.slash")
            .font(.caption.weight(.semibold))
            .foregroundStyle(PFTheme.textSecondary)
            .frame(maxWidth: .infinity, alignment: .leading)
            .accessibilityIdentifier("state.offline")
    }

    private var label: String {
        guard let lastUpdatedAt else { return "Offline · Downloaded data" }
        return "Offline · Updated \(lastUpdatedAt.formatted(date: .abbreviated, time: .shortened))"
    }
}

enum PFAccessibility {
    static func progress(reviewed: Int, total: Int) -> String {
        "\(reviewed) of \(total) papers reviewed"
    }

    static func paperCount(_ count: Int) -> String {
        "\(count) \(count == 1 ? "paper" : "papers")"
    }
}
