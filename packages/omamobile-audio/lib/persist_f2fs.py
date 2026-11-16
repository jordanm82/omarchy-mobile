#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read a file from an unmounted F2FS partition strictly read-only.

Used when persist (/dev/sda1 on zumapro/caiman) is formatted with F2FS
instead of ext4, so debugfs cannot open it and mounting persist is never
needed or permitted.
"""

import struct
import sys

F2FS_SUPER_OFFSET = 1024
F2FS_SUPER_MAGIC = 0xF2F52010
F2FS_CP_BITMAP_OFFSET = 192
F2FS_INLINE_XATTR = 0x01
F2FS_INLINE_DATA = 0x02
F2FS_INLINE_DENTRY = 0x04
F2FS_EXTRA_ATTR = 0x20
NAT_ENTRIES_PER_BLK = 455
F2FS_DENTRIES_PER_BLK = 214
F2FS_INLINE_XATTR_DEFAULT = 200
F2FS_NODE_ADDR_START = 360
F2FS_NODE_FOOTER_OFF = 4072
F2FS_INODE_ADDR_END = 4052


class F2FSReader:
    """Minimal read-only F2FS reader for checkpointed small calibration files."""

    def __init__(self, f):
        self.f = f
        f.seek(F2FS_SUPER_OFFSET)
        sb = f.read(1024)
        if len(sb) < 128:
            raise ValueError("truncated F2FS superblock")
        magic, _, _, _, _, log_bsz, log_bps = struct.unpack_from("<IHH4I", sb, 0)
        if magic != F2FS_SUPER_MAGIC:
            raise ValueError(f"not F2FS (magic 0x{magic:08x})")
        self.bsz = 1 << log_bsz
        self.bps = 1 << log_bps
        (
            _, _, _, _, _, _, self.cp_blk, _, self.nat_blk, _, _, self.root_ino
        ) = struct.unpack_from("<12I", sb, 52)
        self.nat_bits = self._read_best_cp()

    def _blk(self, blkaddr):
        self.f.seek(blkaddr * self.bsz)
        data = self.f.read(self.bsz)
        if len(data) != self.bsz:
            raise EOFError(f"short read at block {blkaddr}")
        return data

    def _read_best_cp(self):
        best = None
        for pack in range(2):
            base = self.cp_blk + pack * self.bps
            hdr = self._blk(base)
            ver = struct.unpack_from("<Q", hdr, 0)[0]
            tot_blk, _, _, _, _, sit_bytes, nat_bytes, _ = struct.unpack_from(
                "<8I", hdr, 136
            )
            if tot_blk < 2 or tot_blk > self.bps:
                continue
            ftr = self._blk(base + tot_blk - 1)
            fver = struct.unpack_from("<Q", ftr, 0)[0]
            if ver != fver:
                continue
            bm_start = F2FS_CP_BITMAP_OFFSET + sit_bytes
            nat_bm = hdr[bm_start : bm_start + nat_bytes]
            if best is None or ver > best[0]:
                best = (ver, nat_bm)
        if best is None:
            raise ValueError("no valid F2FS checkpoint")
        return best[1]

    def nid_to_blk(self, nid):
        blk_idx = nid // NAT_ENTRIES_PER_BLK
        off = (nid % NAT_ENTRIES_PER_BLK) * 9
        byte_idx = blk_idx >> 3
        use_set1 = (
            bool(self.nat_bits[byte_idx] & (1 << (blk_idx & 7)))
            if byte_idx < len(self.nat_bits)
            else False
        )
        phys_seg = (blk_idx // self.bps) * 2 + (1 if use_set1 else 0)
        blk = self._blk(self.nat_blk + phys_seg * self.bps + (blk_idx % self.bps))
        return struct.unpack_from("<BII", blk, off)[2]

    def _read_inode(self, ino):
        blkaddr = self.nid_to_blk(ino)
        if blkaddr == 0:
            raise FileNotFoundError(ino)
        blk = self._blk(blkaddr)
        inline = blk[3]
        size = struct.unpack_from("<Q", blk, 16)[0]
        extra_isize = 0
        xattr_sz = 0
        if inline & F2FS_EXTRA_ATTR:
            extra_isize, inline_xattr_4b = struct.unpack_from(
                "<HH", blk, F2FS_NODE_ADDR_START
            )
            if inline & F2FS_INLINE_XATTR:
                xattr_sz = (inline_xattr_4b * 4) if inline_xattr_4b else F2FS_INLINE_XATTR_DEFAULT
        elif inline & F2FS_INLINE_XATTR:
            xattr_sz = F2FS_INLINE_XATTR_DEFAULT
        return blk, inline, size, extra_isize, xattr_sz

    @staticmethod
    def _scan_dentries(bm, nr, dentries_off, names_off, buf, target):
        i = 0
        while i < nr:
            if not (bm[i >> 3] & (1 << (i & 7))):
                i += 1
                continue
            _, ino, name_len, _ = struct.unpack_from(
                "<IIHB", buf, dentries_off + i * 11
            )
            nm = buf[names_off + i * 8 : names_off + i * 8 + name_len]
            if nm == target:
                return ino
            i += max(1, (name_len + 7) // 8)
        return None

    def _lookup(self, dir_ino, name_bytes):
        blk, inline, _, extra_isize, xattr_sz = self._read_inode(dir_ino)
        data_end = F2FS_INODE_ADDR_END - xattr_sz
        if inline & F2FS_INLINE_DENTRY:
            area = blk[F2FS_NODE_ADDR_START + extra_isize + 4 : data_end]
            nr = (len(area) * 8) // (19 * 8 + 1)
            bmsz = (nr + 7) // 8
            names_off = len(area) - nr * 8
            dentries_off = names_off - nr * 11
            return self._scan_dentries(
                area[:bmsz], nr, dentries_off, names_off, area, name_bytes
            )
        addr_cnt = (data_end - (F2FS_NODE_ADDR_START + extra_isize)) // 4
        for idx in range(addr_cnt):
            baddr = struct.unpack_from(
                "<I", blk, F2FS_NODE_ADDR_START + extra_isize + idx * 4
            )[0]
            if baddr == 0:
                continue
            dblk = self._blk(baddr)
            ino = self._scan_dentries(
                dblk[:27],
                F2FS_DENTRIES_PER_BLK,
                30,
                30 + F2FS_DENTRIES_PER_BLK * 11,
                dblk,
                name_bytes,
            )
            if ino is not None:
                return ino
        return None

    def read_file(self, path):
        cur = self.root_ino
        for part in [p for p in path.split("/") if p]:
            cur = self._lookup(cur, part.encode("utf-8"))
            if cur is None:
                return None
        blk, inline, size, extra_isize, xattr_sz = self._read_inode(cur)
        data_end = F2FS_INODE_ADDR_END - xattr_sz
        if inline & F2FS_INLINE_DATA:
            start = F2FS_NODE_ADDR_START + extra_isize + 4
            if start + size > data_end:
                raise ValueError("corrupt inline data size")
            return blk[start : start + size]
        out = bytearray()
        addr_cnt = (data_end - (F2FS_NODE_ADDR_START + extra_isize)) // 4
        for idx in range(addr_cnt):
            if len(out) >= size:
                break
            baddr = struct.unpack_from(
                "<I", blk, F2FS_NODE_ADDR_START + extra_isize + idx * 4
            )[0]
            if baddr == 0:
                break
            out.extend(self._blk(baddr))
        if len(out) < size:
            raise ValueError("file exceeds direct blocks (not supported)")
        return bytes(out[:size])


def main():
    if len(sys.argv) != 3:
        sys.stderr.write("usage: persist_f2fs.py <block-dev> <path>\n")
        return 1
    try:
        with open(sys.argv[1], "rb") as f:
            data = F2FSReader(f).read_file(sys.argv[2])
    except Exception as exc:
        sys.stderr.write(f"persist_f2fs: {exc}\n")
        return 1
    if data is None:
        sys.stderr.write(f"persist_f2fs: {sys.argv[2]}: File not found\n")
        return 2
    sys.stdout.buffer.write(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
