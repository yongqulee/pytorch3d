#!/usr/bin/env python3
# Copyright (c) Facebook, Inc. and its affiliates. All rights reserved.
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.

import torch
import torch.nn.functional as F


def vert_align(
    feats,
    verts,
    return_packed: bool = False,
    interp_mode: str = "bilinear",
    padding_mode: str = "zeros",
) -> torch.Tensor:
    """
    Sample vertex features from a feature map. This operation is called
    "perceptual feaure pooling" in [1] or "vert align" in [2].

    [1] Wang et al, "Pixel2Mesh: Generating 3D Mesh Models from Single
        RGB Images", ECCV 2018.
    [2] Gkioxari et al, "Mesh R-CNN", ICCV 2019

    Args:
        feats: FloatTensor of shape (N, C, H, W) representing image features
            from which to sample or a list of features each with potentially
            different C, H or W dimensions.
        verts: FloatTensor of shape (N, V, 3) or an object (e.g. Meshes) with
            'verts_padded' as an attribute giving the (x, y, z) vertex positions
            for which to sample. (x, y) verts should be normalized such that
            (-1, -1) corresponds to top-left and (+1, +1) to bottom-right
            location in the input feature map.
        return_packed: (bool) Indicates whether to return packed features
        interp_mode: (str) Specifies how to interpolate features.
            ('bilinear' or 'nearest')
        padding_mode: (str) Specifies how to handle vertices outside of the
            [-1, 1] range. ('zeros', 'reflection', or 'border')

    Returns:
        feats_sampled: FloatTensor of shape (N, V, C) giving sampled features for
        each vertex. If feats is a list, we return concatentated
        features in axis=2 of shape (N, V, sum(C_n)) where
        C_n = feats[n].shape[1]. If return_packed = True, the
        features are transformed to a packed representation
        of shape (sum(V), C)

    """
    if torch.is_tensor(verts):
        if verts.dim() != 3:
            raise ValueError("verts tensor should be 3 dimensional")
        grid = verts
    elif hasattr(verts, "verts_padded"):
        grid = verts.verts_padded()
    else:
        raise ValueError(
            "verts must be a tensor or have a `verts_padded` attribute"
        )

    grid = grid[:, None, :, :2]  # (N, 1, V, 2)

    if torch.is_tensor(feats):
        feats = [feats]
    for feat in feats:
        if feat.dim() != 4:
            raise ValueError("feats must have shape (N, C, H, W)")
        if grid.shape[0] != feat.shape[0]:
            raise ValueError("inconsistent batch dimension")

    feats_sampled = []
    for feat in feats:
        feat_sampled = F.grid_sample(
            feat, grid, mode=interp_mode, padding_mode=padding_mode
        )  # (N, C, 1, V)
        feat_sampled = feat_sampled.squeeze(dim=2).transpose(1, 2)  # (N, V, C)
        feats_sampled.append(feat_sampled)
    feats_sampled = torch.cat(feats_sampled, dim=2)  # (N, V, sum(C))

    if return_packed:
        # flatten the first two dimensions: (N*V, C)
        feats_sampled = feats_sampled.view(-1, feats_sampled.shape[-1])
        if hasattr(verts, "verts_padded_to_packed_idx"):
            idx = (
                verts.verts_padded_to_packed_idx()
                .view(-1, 1)
                .expand(-1, feats_sampled.shape[-1])
            )
            feats_sampled = feats_sampled.gather(0, idx)  # (sum(V), C)

    return feats_sampled
