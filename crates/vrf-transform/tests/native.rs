//! Compare legacy transforms with the original executable's machine code.

include!("data/native_vectors.rs");

use vrf_bitio::BitReader;
use vrf_transform::TransformVersion;

fn bytes(hex: &str) -> Vec<u8> {
    (0..hex.len())
        .step_by(2)
        .map(|i| u8::from_str_radix(&hex[i..i + 2], 16).unwrap())
        .collect()
}

#[test]
fn transforms_match_native_machine_code() {
    for &(branch, bits, seed, input, expected) in NATIVE_VECTORS {
        let version = TransformVersion::require(branch).expect("native build is registered");
        let input = bytes(input);
        let mut output = vec![0; bits.div_ceil(8)];
        version
            .decode_from(&mut BitReader::new(&input), bits, seed, &mut output)
            .unwrap();
        assert_eq!(
            output,
            bytes(expected),
            "{branch}, bits={bits}, seed={seed:#x}"
        );
    }
}
