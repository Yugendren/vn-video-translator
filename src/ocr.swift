import Foundation
import AVFoundation
import Vision

// Usage: ocr_bin <video_path> <output_json_path> [interval_sec] [crop_y_ratio] [crop_h_ratio] [langs_comma_separated]
let args = CommandLine.arguments

guard args.count >= 3 else {
    print("Usage: ocr_bin <video_path> <output_json_path> [interval_sec] [crop_y_ratio] [crop_h_ratio] [langs]")
    exit(1)
}

let videoPath = args[1]
let outPath = args[2]
let intervalSec = args.count > 3 ? (Double(args[3]) ?? 1.0) : 1.0
let cropYRatio = args.count > 4 ? (Double(args[4]) ?? 0.72) : 0.72
let cropHRatio = args.count > 5 ? (Double(args[5]) ?? 0.28) : 0.28
let langArg = args.count > 6 ? args[6] : "zh-Hans,en-US"
let languages = langArg.split(separator: ",").map { String($0) }

let videoURL = URL(fileURLWithPath: videoPath)
let asset = AVURLAsset(url: videoURL)
let generator = AVAssetImageGenerator(asset: asset)
generator.appliesPreferredTrackTransform = true
generator.requestedTimeToleranceBefore = CMTime(seconds: 0.1, preferredTimescale: 600)
generator.requestedTimeToleranceAfter = CMTime(seconds: 0.1, preferredTimescale: 600)

let durationSec = CMTimeGetSeconds(asset.duration)
print("Video duration: \(String(format: "%.2f", durationSec)) seconds")
print("Sampling interval: \(intervalSec)s | Languages: \(languages.joined(separator: ", "))")

let request = VNRecognizeTextRequest()
request.recognitionLanguages = languages
request.recognitionLevel = .accurate

struct FrameData: Codable {
    let time: Double
    let lines: [String]
}

var allFrames: [FrameData] = []
var currentTime = 3.0 // Skip first 3 seconds of intro / menu

let startTime = CFAbsoluteTimeGetCurrent()
var lastReport = startTime

while currentTime < durationSec {
    let t = CMTime(seconds: currentTime, preferredTimescale: 600)
    if let cgImage = try? generator.copyCGImage(at: t, actualTime: nil) {
        let h = CGFloat(cgImage.height)
        let w = CGFloat(cgImage.width)
        let cropY = Int(h * CGFloat(cropYRatio))
        let cropH = Int(h * CGFloat(cropHRatio))
        let cropRect = CGRect(x: 0, y: cropY, width: Int(w), height: min(cropH, Int(h) - cropY))
        
        if let cropped = cgImage.cropping(to: cropRect) {
            let handler = VNImageRequestHandler(cgImage: cropped, options: [:])
            try? handler.perform([request])
            let results = (request.results as? [VNRecognizedTextObservation] ?? [])
            var lines: [String] = []
            for obs in results {
                if let text = obs.topCandidates(1).first?.string {
                    lines.append(text)
                }
            }
            if !lines.isEmpty {
                allFrames.append(FrameData(time: currentTime, lines: lines))
            }
        }
    }
    
    let now = CFAbsoluteTimeGetCurrent()
    if now - lastReport >= 3.0 {
        let pct = (currentTime / durationSec) * 100.0
        let speed = (currentTime - 3.0) / max(now - startTime, 0.001)
        let eta = (durationSec - currentTime) / max(speed, 0.001)
        print(String(format: "Progress: %.1f%% (t=%.0fs/%.0fs) | Speed: %.1fx | ETA: %.0fs | Frames: %d", pct, currentTime, durationSec, speed, eta, allFrames.count))
        fflush(stdout)
        lastReport = now
    }
    
    currentTime += intervalSec
}

let outURL = URL(fileURLWithPath: outPath)
let encoder = JSONEncoder()
encoder.outputFormatting = .prettyPrinted
if let data = try? encoder.encode(allFrames) {
    try? data.write(to: outURL)
    print("Done! Saved \(allFrames.count) OCR frames to \(outPath)")
} else {
    print("Error saving output JSON to \(outPath)")
    exit(1)
}
EOF
