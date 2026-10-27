const motorcyclePatterns = [
    /^\d{4}[A-Z]{2}$/,       // Legacy MC (e.g., 2724SO)
    /^[A-Z]{2}\d{5}$/,       // 2 Letters, 5 Numbers (AB12345)
    /^[A-Z]{3}\d{5}$/,       // 3 Letters, 5 Numbers (ABC12345)
    /^[A-Z]\d{5}[A-Z]$/,     // 1 Letter, 5 Numbers, 1 Letter (N12345A)
    /^\d{3}[A-Z]{3}$/,       // 3 Numbers, 3 Letters (123ABC)
    /^[A-Z]\d{3}[A-Z]{2}$/,  // A 123 BC
    /^[A-Z]{2}\d{3}[A-Z]$/,  // AB 123 C
    /^\d[A-Z]{3}\d{2}$/,     // 1 ABC 23
    /^[A-Z]\d{4}[A-Z]$/,     // A 1234 C
    /^[A-Z]\d[A-Z]\d{3}$/,   // A 1 C 234
    /^[A-Z]{2}\d{2}[A-Z]\d{2}$/ // A 12 C 34
]

const carPatterns = [
    // --- Standard 4-Wheel MV Formats ---
    /^[A-Z]{3}\d{4}$/,       // 3 Letters, 4 Numbers (ABC1234)
    /^[A-Z]{3}\d{3}$/,       // 3 Letters, 3 Numbers (WFU799)
    /^[A-Z]{2}\d{4}$/,       // 2 Letters, 4 Numbers (Government/Electric/Conduction SE1234)

    // --- Conduction Stickers & Temporary Plates ---
    /^[A-Z]\d{4}$/,          // 1 Letter, 4 Numbers (Legacy Conduction)

    // --- LTO MV File Numbers (Temporary registrations) ---
    /^\d{11}$/,              // 11-Digit Pure Numerical File Block (13010000123)
    /^\d{10}$/,              // 10-Digit Pure Numerical File Block

    // --- Protocol & Diplomatic Formats ---
    /^\d{1,2}$/,             // 1 to 2 Digit Government Protocol Keys (1 to 16)
    /^\d{7}$/                // 7-Digit Diplomatic Plates (1234567)
]

const isValidPlateFormat = (plate) => {
    if (!plate || typeof plate !== 'string') return false
    const clean = plate.replace(/[\s-]+/g, '').toUpperCase()
    if (!clean) return false
    return motorcyclePatterns.some(pattern => pattern.test(clean)) || carPatterns.some(pattern => pattern.test(clean))
}