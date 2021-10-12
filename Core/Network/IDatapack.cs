﻿using System.Diagnostics.CodeAnalysis;

namespace ChattingRoom.Core.Networks;
public interface IDatapack
{
    public byte[] ToBytes();

    public bool CanWrite { get; }
    public void Write(byte[] bytes);

    public void Write(byte b);

    public bool IsEmpty { get; }

    public int Length { get; }

    public void WriteInto([NotNull] Stream stream);
}

public static class Datapack
{
    public static IDatapack Empty
    {
        get;
    } = new EmptyDatapack();

    public static IDatapack ReadOne([NotNull] Stream stream)
    {
        if (!stream.CanRead)
        {
            return Empty;
        }
        const int IntSize = sizeof(int);
        var dataLength_Bytes = new byte[IntSize];
        try
        {
            stream.Read(dataLength_Bytes, 0, IntSize);
            int dataLength = BitConverter.ToInt32(dataLength_Bytes);
            var data = new byte[dataLength];
            stream.Read(data, 0, dataLength);
            return new ReadOnlyDatapck(data);
        }
        catch (Exception)
        {
            return Empty;
        }
    }

    public static IDatapack Write([NotNull] this IDatapack datapack, int data)
    {
        datapack.Write(BitConverter.GetBytes(data));
        return datapack;
    }
    public static IDatapack Write([NotNull] this IDatapack datapack, short data)
    {
        datapack.Write(BitConverter.GetBytes(data));
        return datapack;
    }
    public static IDatapack Write([NotNull] this IDatapack datapack, long data)
    {
        datapack.Write(BitConverter.GetBytes(data));
        return datapack;
    }
    public static IDatapack Write([NotNull] this IDatapack datapack, float data)
    {
        datapack.Write(BitConverter.GetBytes(data));
        return datapack;
    }
    public static IDatapack Write([NotNull] this IDatapack datapack, double data)
    {
        datapack.Write(BitConverter.GetBytes(data));
        return datapack;
    }

    private class EmptyDatapack : IDatapack
    {
        public bool IsEmpty => true;

        public int Length => 0;

        public bool CanWrite => throw new NotImplementedException();

        public byte[] ToBytes() => Array.Empty<byte>();

        public void Write(byte[] bytes)
        {

        }

        public void Write(byte b)
        {

        }

        public void WriteInto([NotNull] Stream stream)
        {

        }
    }
}
