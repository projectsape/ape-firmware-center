// Minimal, dependency-free MD5 (RFC 1321) for Uint8Array input.
// Used only to verify flash writes against the chip's SPI MD5 command.
// The Web Crypto API intentionally excludes MD5, hence this small impl.

const K = new Int32Array([
  -680876936, -389564586, 606105819, -1044525330, -176418897, 1200080426,
  -1473231341, -45705983, 1770035416, -1958414417, -42063, -1990404162,
  1804603682, -40341101, -1502002290, 1236535329,
  -165796510, -1069501632, 643717713, -373897302, -701558691, 38016083,
  -660478335, -405537848, 568446438, -1019803690, -187363961, 1163531501,
  -1444681467, -51403784, 1735328473, -1926607734,
  -378558, -2022574463, 1839030562, -35309556, -1530992060, 1272893353,
  -155497632, -1094730640, 681279174, -358537222, -722521979, 76029189,
  -640364487, -421815835, 530742520, -995338651,
  -198630844, 1126891415, -1416354905, -57434055, 1700485571, -1894986606,
  -1051523, -2054922799, 1873313359, -30611744, -1560198380, 1309151649,
  -145523070, -1120210379, 718787259, -343485551,
]);

const S = [
  7, 12, 17, 22, 7, 12, 17, 22, 7, 12, 17, 22, 7, 12, 17, 22,
  5, 9, 14, 20, 5, 9, 14, 20, 5, 9, 14, 20, 5, 9, 14, 20,
  4, 11, 16, 23, 4, 11, 16, 23, 4, 11, 16, 23, 4, 11, 16, 23,
  6, 10, 15, 21, 6, 10, 15, 21, 6, 10, 15, 21, 6, 10, 15, 21,
];

function rotl(x, c) {
  return (x << c) | (x >>> (32 - c));
}

export function md5Hex(data) {
  // data: Uint8Array (or ArrayBuffer)
  const bytes = data instanceof Uint8Array ? data : new Uint8Array(data);
  const len = bytes.length;

  // Pad: append 0x80, zeros, and 64-bit little-endian bit length.
  const paddedLen = (((len + 8) >> 6) + 1) << 6;
  const padded = new Uint8Array(paddedLen);
  padded.set(bytes);
  padded[len] = 0x80;
  const bitLen = len * 8;
  const dv = new DataView(padded.buffer);
  dv.setUint32(paddedLen - 8, bitLen >>> 0, true);
  dv.setUint32(paddedLen - 4, Math.floor(bitLen / 0x100000000), true);

  const M = new Int32Array(padded.buffer);
  let a0 = 0x67452301;
  let b0 = 0xefcdab89;
  let c0 = 0x98badcfe;
  let d0 = 0x10325476;

  for (let i = 0; i < M.length; i += 16) {
    let A = a0, B = b0, C = c0, D = d0;
    for (let j = 0; j < 64; j++) {
      let F, g;
      if (j < 16) {
        F = (B & C) | (~B & D);
        g = j;
      } else if (j < 32) {
        F = (D & B) | (~D & C);
        g = (5 * j + 1) & 15;
      } else if (j < 48) {
        F = B ^ C ^ D;
        g = (3 * j + 5) & 15;
      } else {
        F = C ^ (B | ~D);
        g = (7 * j) & 15;
      }
      const temp = D;
      D = C;
      C = B;
      B = (B + rotl(A + F + K[j] + M[i + g], S[j])) | 0;
      A = temp;
    }
    a0 = (a0 + A) | 0;
    b0 = (b0 + B) | 0;
    c0 = (c0 + C) | 0;
    d0 = (d0 + D) | 0;
  }

  // Standard MD5 digest: each 32-bit word emitted little-endian (byte order).
  const hex = (w) => {
    const u = w >>> 0;
    let s = "";
    for (let i = 0; i < 4; i++) {
      s += ((u >>> (8 * i)) & 0xff).toString(16).padStart(2, "0");
    }
    return s;
  };
  return hex(a0) + hex(b0) + hex(c0) + hex(d0);
}
