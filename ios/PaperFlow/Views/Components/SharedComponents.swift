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
        .accessibilityValue("\(reviewed) of \(total) papers reviewed")
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
        VStack(spacing: PFTheme.Spacing.standard) {
            ProgressView()
            Text("Loading PaperFlow…")
                .foregroundStyle(PFTheme.textSecondary)
        }
        .frame(maxWidth: .infinity, minHeight: 180)
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

    var body: some View {
        ContentUnavailableView(
            "Unable to Load",
            systemImage: "exclamationmark.triangle",
            description: Text(message)
        )
        .accessibilityIdentifier("state.error")
    }
}
